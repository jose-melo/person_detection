/* Copyright 2019 The TensorFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================*/

#include <TensorFlowLite.h>
#include <ArduinoBLE.h>

#include "main_functions.h"

#include "detection_responder.h"
#include "image_provider.h"
#include "model_settings.h"
#include "person_detect_model_data.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

// Globals, used for compatibility with Arduino-style sketches.
namespace {
tflite::ErrorReporter* error_reporter = nullptr;
const tflite::Model* model = nullptr;
tflite::MicroInterpreter* interpreter = nullptr;
TfLiteTensor* input = nullptr;


BLEService ledService("180A"); // BLE LED Service

// BLE LED Switch Characteristic - custom 128-bit UUID, read and writable by central
BLECharacteristic switchCharacteristic("2A57", BLERead | BLEWrite | BLENotify, 200);
BLEByteCharacteristic imageControlCharacteristic("2A58", BLERead | BLEWrite);


// In order to use optimized tensorflow lite kernels, a signed int8_t quantized
// model is preferred over the legacy unsigned model format. This means that
// throughout this project, input images must be converted from unisgned to
// signed format. The easiest and quickest way to convert from unsigned to
// signed 8-bit integers is to subtract 128 from the unsigned value to get a
// signed value.

// An area of memory to use for input, output, and intermediate arrays.
constexpr int kTensorArenaSize = 136 * 1024;
static uint8_t tensor_arena[kTensorArenaSize];
}  // namespace

// The name of this function is important for Arduino compatibility.
void setup() {
  // Set up logging. Google style is to avoid globals or statics because of
  // lifetime uncertainty, but since this has a trivial destructor it's okay.
  // NOLINTNEXTLINE(runtime-global-variables)
  static tflite::MicroErrorReporter micro_error_reporter;
  error_reporter = &micro_error_reporter;

  // Map the model into a usable data structure. This doesn't involve any
  // copying or parsing, it's a very lightweight operation.
  model = tflite::GetModel(g_person_detect_model_data);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    TF_LITE_REPORT_ERROR(error_reporter,
                         "Model provided is schema version %d not equal "
                         "to supported version %d.",
                         model->version(), TFLITE_SCHEMA_VERSION);
    return;
  }

  // Pull in only the operation implementations we need.
  // This relies on a complete list of all the ops needed by this graph.
  // An easier approach is to just use the AllOpsResolver, but this will
  // incur some penalty in code space for op implementations that are not
  // needed by this graph.
  //
  // tflite::AllOpsResolver resolver;
  // NOLINTNEXTLINE(runtime-global-variables)
  static tflite::MicroMutableOpResolver<5> micro_op_resolver;
  micro_op_resolver.AddAveragePool2D();
  micro_op_resolver.AddConv2D();
  micro_op_resolver.AddDepthwiseConv2D();
  micro_op_resolver.AddReshape();
  micro_op_resolver.AddSoftmax();

  // Build an interpreter to run the model with.
  // NOLINTNEXTLINE(runtime-global-variables)
  static tflite::MicroInterpreter static_interpreter(
      model, micro_op_resolver, tensor_arena, kTensorArenaSize, error_reporter);
  interpreter = &static_interpreter;

  // Allocate memory from the tensor_arena for the model's tensors.
  TfLiteStatus allocate_status = interpreter->AllocateTensors();
  if (allocate_status != kTfLiteOk) {
    TF_LITE_REPORT_ERROR(error_reporter, "AllocateTensors() failed");
    return;
  }

  // Get information about the memory area to use for the model's input.
  input = interpreter->input(0);

    // begin initialization
  if (!BLE.begin()) {
    Serial.println("starting Bluetooth® Low Energy failed!");
    while (1);
  }

    // set advertised local name and service UUID:
  BLE.setLocalName("Nano 33 IoT");
  BLE.setAdvertisedService(ledService);

  // add the characteristic to the service
  ledService.addCharacteristic(switchCharacteristic);
  ledService.addCharacteristic(imageControlCharacteristic);


  // add service
  BLE.addService(ledService);

  // set the initial value for the characteristic:
  //switchCharacteristic.writeValue(0);
  uint8_t initialValue[20] = {0};  // Initialize an array with zeros
  switchCharacteristic.writeValue(initialValue, 20);


  // Event handlers
  // switchCharacteristic.setEventHandler(BLEWritten, onSwitchCharacteristicWritten);
  switchCharacteristic.setEventHandler(BLESubscribed, onSwitchCharacteristicSubscribed);
  switchCharacteristic.setEventHandler(BLEUnsubscribed, onSwitchCharacteristicUnsubscribed);
  imageControlCharacteristic.setEventHandler(BLEWritten, onImageControlCharacteristicWritten);

  // start advertising
  BLE.advertise();

  Serial.println("Nano 33 pronto - peripheral");

}

// The name of this function is important for Arduino compatibility.
void loop() {
   BLEDevice central = BLE.central();

  if (central) {
    Serial.print("Connectado ao nó central: ");
    Serial.println(central.address());
    while (central.connected()) {
      delay(10); // just to avoid super tight loop
    }
    Serial.print("Desconectado do nó central: ");
    Serial.println(central.address());
  }
 
}


void onImageControlCharacteristicWritten(BLEDevice central, BLECharacteristic characteristic) {
  if (characteristic.uuid() == "2A58") { 

    // Initialize all variables
    TfLiteTensor* output;
    int8_t person_score;
    int8_t no_person_score;

    switch (imageControlCharacteristic.value()) {
      case 01:
        Serial.println("LED on");
        //digitalWrite(LED_BUILTIN, HIGH);
        
        // Get image from provider.
        if (kTfLiteOk != GetImage(error_reporter, kNumCols, kNumRows, kNumChannels,
                                  input->data.int8)) {
          TF_LITE_REPORT_ERROR(error_reporter, "Image capture failed.");
        }
        
        sendImage(input->data.int8);

        // Run the model on this input and make sure it succeeds.
        if (kTfLiteOk != interpreter->Invoke()) {
          TF_LITE_REPORT_ERROR(error_reporter, "Invoke failed.");
        }

        output = interpreter->output(0);

        // Process the inference results.
         person_score = output->data.uint8[kPersonIndex];
         no_person_score = output->data.uint8[kNotAPersonIndex];
         RespondToDetection(error_reporter, person_score, no_person_score);
        break;
      default:
        Serial.println(F("LED off"));
        //digitalWrite(LED_BUILTIN, LOW);
        break;
    }
  }
}

void sendImage(int8* image) {
  const int CHUNK_SIZE = 200;
  uint8_t buffer[CHUNK_SIZE];

  for (int i = 0; i < 96*96; i += CHUNK_SIZE) {
    int chunkLength = min(CHUNK_SIZE, (96*96) - i);
    
    for (int j = 0; j < chunkLength; j++) {
      buffer[j] = image[i + j];
    }

    switchCharacteristic.writeValue(buffer, CHUNK_SIZE);  // Now it directly takes the buffer
    
    delay(50);  // Adjust the delay as needed
  }

  delay(2000);
}


//void sendImage(int8* image) {
  //for (int i = 0; i < 96*96; i++) {
      //switchCharacteristic.writeValue(image[i]);
      ////Serial.print("Sent: ");
      ////Serial.println(image[i]);
      //delay(1);  // Adjust the delay as needed
    
  //}
  //switchCharacteristic.writeValue(0); 
//}


void onSwitchCharacteristicSubscribed(BLEDevice central, BLECharacteristic characteristic) {
  Serial.println(F("Nó central se inscreveu para receber notificações"));
}

void onSwitchCharacteristicUnsubscribed(BLEDevice central, BLECharacteristic characteristic) {
  Serial.println(F("Nó central se desinscreveu"));
}

