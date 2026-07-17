cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(TG_CONTROLLER C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(TG_CONTROLLER
    firmware/controller/main.c
    firmware/controller/usb_descriptors.c
)

target_include_directories(TG_CONTROLLER PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/controller
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)

target_link_libraries(TG_CONTROLLER
    pico_stdlib
    tinyusb_device
    tinyusb_board
)

pico_enable_stdio_usb(TG_CONTROLLER 0)
pico_enable_stdio_uart(TG_CONTROLLER 0)
pico_add_extra_outputs(TG_CONTROLLER)

add_executable(TG_GUN_P1
    firmware/gun_p1/main.c
    firmware/gun_p1/usb_descriptors.c
)

target_include_directories(TG_GUN_P1 PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/gun_p1
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)

target_link_libraries(TG_GUN_P1
    pico_stdlib
    hardware_adc
    tinyusb_device
    tinyusb_board
)

pico_enable_stdio_usb(TG_GUN_P1 0)
pico_enable_stdio_uart(TG_GUN_P1 0)
pico_add_extra_outputs(TG_GUN_P1)
