cmake_minimum_required(VERSION 3.10)
project(PixiuManagement LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt5 REQUIRED COMPONENTS Widgets Network)
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" PIXIU_MANAGEMENT_VERSION LIMIT_COUNT 1)
add_library(pixiu-management STATIC
    MemoryWorkspace.h MemoryWorkspace.cpp
    MemoryWriteDialog.h MemoryWriteDialog.cpp
    MemoryAudit.h MemoryAudit.cpp
    ../src/services/BackendTransport.h ../src/services/BackendTransport.cpp
    ../src/services/HttpBackendTransport.h ../src/services/HttpBackendTransport.cpp)
target_include_directories(pixiu-management PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src")
target_compile_definitions(pixiu-management PRIVATE PIXIU_VERSION="${PIXIU_MANAGEMENT_VERSION}")
target_link_libraries(pixiu-management PUBLIC Qt5::Widgets Qt5::Network)
option(PIXIU_MANAGEMENT_TESTS "Build embedded management tests" OFF)
if(PIXIU_MANAGEMENT_TESTS)
    enable_testing()
    find_package(Qt5 REQUIRED COMPONENTS Test)
    add_executable(t_memory_workspace tests/t_memory_workspace.cpp)
    target_link_libraries(t_memory_workspace PRIVATE pixiu-management Qt5::Test)
    add_test(NAME memory_workspace COMMAND t_memory_workspace)
    set_tests_properties(memory_workspace PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
