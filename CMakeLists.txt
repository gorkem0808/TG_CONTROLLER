cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(TG_CONTROLLER_PRO_V4_4 C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

function(tg_apply_common target)
    target_compile_definitions(${target} PRIVATE
        PICO_STDIO_USB=0
        PICO_STDIO_UART=0
    )
    target_compile_options(${target} PRIVATE
        -Wall
        -Wextra
        -Werror
    )
    pico_add_extra_outputs(${target})
endfunction()

add_executable(TG_CONTROLLER
    firmware/controller/main.c
    firmware/common/usb_descriptors.c
)
target_include_directories(TG_CONTROLLER PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)
target_link_libraries(TG_CONTROLLER
    pico_stdlib
    hardware_flash
    hardware_sync
    tinyusb_device
    tinyusb_board
)
tg_apply_common(TG_CONTROLLER)

add_executable(TG_GUN_P1
    firmware/gun/main.c
    firmware/gun/usb_descriptors.c
)
target_include_directories(TG_GUN_P1 PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/gun
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)
target_compile_definitions(TG_GUN_P1 PRIVATE TG_PLAYER_ID=1)
target_link_libraries(TG_GUN_P1
    pico_stdlib
    hardware_adc
    hardware_flash
    hardware_sync
    m
    tinyusb_device
    tinyusb_board
)
tg_apply_common(TG_GUN_P1)

add_executable(TG_GUN_P2
    firmware/gun/main.c
    firmware/gun/usb_descriptors.c
)
target_include_directories(TG_GUN_P2 PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/firmware/gun
    ${CMAKE_CURRENT_LIST_DIR}/firmware/common
)
target_compile_definitions(TG_GUN_P2 PRIVATE TG_PLAYER_ID=2)
target_link_libraries(TG_GUN_P2
    pico_stdlib
    hardware_adc
    hardware_flash
    hardware_sync
    m
    tinyusb_device
    tinyusb_board
)
tg_apply_common(TG_GUN_P2)
