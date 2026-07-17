cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(TG_CONTROLLER C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# ------------------------------------------------------------
# Main arcade controller
# ------------------------------------------------------------
add_executable(TG_CONTROLLER
    firmware/controller/main.c
    firmware/common/usb_descriptors.c
)

target_include_directories(TG_CONTROLLER PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)

target_compile_definitions(TG_CONTROLLER PRIVATE
    PICO_STDIO_USB=0
    PICO_STDIO_UART=0
)

target_compile_options(TG_CONTROLLER PRIVATE
    -Wall
    -Wextra
    -Werror
)

target_link_libraries(TG_CONTROLLER
    pico_stdlib
    tinyusb_device
    tinyusb_board
)

pico_add_extra_outputs(TG_CONTROLLER)

# ------------------------------------------------------------
# Player 1 gun
# ------------------------------------------------------------
add_executable(TG_GUN_P1
    firmware/gun_p1/main.c
    firmware/gun_p1/usb_descriptors.c
)

target_include_directories(TG_GUN_P1 PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/gun_p1
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)

target_compile_definitions(TG_GUN_P1 PRIVATE
    PICO_STDIO_USB=0
    PICO_STDIO_UART=0
)

target_compile_options(TG_GUN_P1 PRIVATE
    -Wall
    -Wextra
    -Werror
)

target_link_libraries(TG_GUN_P1
    pico_stdlib
    hardware_adc
    tinyusb_device
    tinyusb_board
)

pico_add_extra_outputs(TG_GUN_P1)
