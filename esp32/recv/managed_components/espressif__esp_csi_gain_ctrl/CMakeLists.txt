if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/esp_csi_gain_ctrl.c")
set(sources "src/esp_csi_gain_ctrl.c")
else()
set(sources "")
endif()

idf_component_register( SRCS "${sources}"
                        INCLUDE_DIRS "include")

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/esp_csi_gain_ctrl.c")
    set(binary_dir "${CMAKE_CURRENT_SOURCE_DIR}/${IDF_VERSION_MAJOR}.${IDF_VERSION_MINOR}/${CONFIG_IDF_TARGET}")
    if(NOT EXISTS "${binary_dir}/libesp_csi_gain_ctrl.a" AND
       "${IDF_VERSION_MAJOR}.${IDF_VERSION_MINOR}" VERSION_EQUAL "6.1")
        set(binary_dir "${CMAKE_CURRENT_SOURCE_DIR}/6.0/${CONFIG_IDF_TARGET}")
    endif()
    if(NOT EXISTS "${binary_dir}/libesp_csi_gain_ctrl.a")
        message(FATAL_ERROR
                "esp_csi_gain_ctrl has no prebuilt library for ESP-IDF "
                "${IDF_VERSION_MAJOR}.${IDF_VERSION_MINOR} and target ${CONFIG_IDF_TARGET}")
    endif()
    add_prebuilt_library(esp_csi_gain_ctrl_lib "${binary_dir}/libesp_csi_gain_ctrl.a")
    target_include_directories(${COMPONENT_LIB} INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/include")
    target_link_libraries(${COMPONENT_LIB} INTERFACE esp_csi_gain_ctrl_lib)
else()
    include(package_manager)
    cu_pkg_define_version(${CMAKE_CURRENT_LIST_DIR})
    target_compile_options(${COMPONENT_LIB} PRIVATE -DLOG_LOCAL_LEVEL=ESP_LOG_DEBUG  -Wignored-qualifiers)
endif()
