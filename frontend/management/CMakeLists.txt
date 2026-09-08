cmake_minimum_required(VERSION 3.10)
project(PixiuManagement LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt5 REQUIRED COMPONENTS Widgets Network WebSockets)
find_path(PIXIU_QRENCODE_INCLUDE_DIR qrencode.h)
find_library(PIXIU_QRENCODE_LIBRARY qrencode)
if(NOT PIXIU_QRENCODE_INCLUDE_DIR OR NOT PIXIU_QRENCODE_LIBRARY)
    message(FATAL_ERROR "libqrencode development files are required for device pairing")
endif()
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" PIXIU_MANAGEMENT_VERSION LIMIT_COUNT 1)
add_library(pixiu-management STATIC
    HostTray.h HostTray.cpp
    HostWindowPin.h HostWindowPin.cpp
    ../src/app/ShortcutManager.h ../src/app/ShortcutManager.cpp
    ../src/services/NotifyService.h ../src/services/NotifyService.cpp
    BackendEventStatus.h BackendEventStatus.cpp
    ../src/services/WebSocketClient.h ../src/services/WebSocketClient.cpp
    AgentEvidence.h AgentEvidence.cpp
    AgentEvidenceClient.h AgentEvidenceClient.cpp
    MemoryScopes.h
    MemoryScopeControl.h MemoryScopeControl.cpp
    HostCloseGuard.h HostCloseGuard.cpp
    ../src/app/ProductInformation.h
    ../src/widgets/InfoDialog.h ../src/widgets/InfoDialog.cpp
    MemoryWorkspace.h MemoryWorkspace.cpp
    MemoryWriteDialog.h MemoryWriteDialog.cpp
    MemoryEditDialog.h MemoryEditDialog.cpp
    MemoryAudit.h MemoryAudit.cpp
    PrivacyPage.h PrivacyPage.cpp
    DevicePage.h DevicePage.cpp
    PairingDialog.h PairingDialog.cpp
    DeliveryPage.h DeliveryPage.cpp
    ForgetPage.h ForgetPage.cpp
    SettingsWorkspace.h SettingsWorkspace.cpp
    ServiceStatusPage.h ServiceStatusPage.cpp
    ../src/app/UpgradeController.h ../src/app/UpgradeController.cpp
    ../src/app/UpgradeUtils.h ../src/app/UpgradeUtils.cpp
    ../src/widgets/CheckUpdateDialog.h ../src/widgets/CheckUpdateDialog.cpp
    ../src/services/BackendTransport.h ../src/services/BackendTransport.cpp
    ../src/services/HttpBackendTransport.h ../src/services/HttpBackendTransport.cpp)
target_include_directories(pixiu-management PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../src")
target_compile_definitions(pixiu-management PRIVATE PIXIU_VERSION="${PIXIU_MANAGEMENT_VERSION}")
target_link_libraries(pixiu-management PUBLIC Qt5::Widgets Qt5::Network Qt5::WebSockets)
target_include_directories(pixiu-management PRIVATE "${PIXIU_QRENCODE_INCLUDE_DIR}")
target_link_libraries(pixiu-management PRIVATE "${PIXIU_QRENCODE_LIBRARY}")
if(PIXIU_HAVE_KYSDK)
    find_package(Qt5 REQUIRED COMPONENTS DBus)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(PIXIU_SHORTCUT REQUIRED IMPORTED_TARGET kysdk-shortcut)
    pkg_check_modules(PIXIU_NOTIFICATION REQUIRED IMPORTED_TARGET kysdk-notification)
    pkg_check_modules(PIXIU_WINDOWMANAGER REQUIRED IMPORTED_TARGET kysdk-waylandhelper)
    find_package(KF5WindowSystem REQUIRED)
    target_compile_definitions(pixiu-management PRIVATE PIXIU_HAVE_KYSDK=1)
    target_link_libraries(pixiu-management PRIVATE PkgConfig::PIXIU_SHORTCUT)
    target_link_libraries(pixiu-management PRIVATE PkgConfig::PIXIU_NOTIFICATION)
    target_link_libraries(pixiu-management PRIVATE PkgConfig::PIXIU_WINDOWMANAGER KF5::WindowSystem)
    target_link_libraries(pixiu-management PRIVATE Qt5::DBus)
endif()
option(PIXIU_MANAGEMENT_TESTS "Build embedded management tests" OFF)
if(PIXIU_MANAGEMENT_TESTS)
    enable_testing()
    find_package(Qt5 REQUIRED COMPONENTS Test)
    foreach(pin_variant IN ITEMS qt kylin_fixture)
        add_executable(t_host_window_pin_${pin_variant} tests/t_host_window_pin.cpp
            HostWindowPin.h HostWindowPin.cpp)
        target_include_directories(t_host_window_pin_${pin_variant} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
        target_link_libraries(t_host_window_pin_${pin_variant} PRIVATE Qt5::Widgets Qt5::Test)
        if(pin_variant STREQUAL "kylin_fixture")
            target_sources(t_host_window_pin_${pin_variant} PRIVATE tests/fixtures/windowmanager/windowmanager.h)
            target_include_directories(t_host_window_pin_${pin_variant} PRIVATE tests/fixtures)
            target_compile_definitions(t_host_window_pin_${pin_variant} PRIVATE PIXIU_HAVE_KYSDK=1)
        else()
            target_compile_options(t_host_window_pin_${pin_variant} PRIVATE -UPIXIU_HAVE_KYSDK)
        endif()
        add_test(NAME host_window_pin_${pin_variant} COMMAND t_host_window_pin_${pin_variant})
        set_tests_properties(host_window_pin_${pin_variant} PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    endforeach()
    # Deterministic fallback tests must not register desktop-global bindings.
    add_executable(t_shortcut_manager ../tests/t_shortcut_manager.cpp ../src/app/ShortcutManager.cpp)
    target_include_directories(t_shortcut_manager PRIVATE ../src)
    target_link_libraries(t_shortcut_manager PRIVATE Qt5::Widgets Qt5::Test)
    target_compile_options(t_shortcut_manager PRIVATE -UPIXIU_HAVE_KYSDK)
    add_test(NAME shortcut_manager COMMAND t_shortcut_manager)
    set_tests_properties(shortcut_manager PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_shortcut_kylin ../tests/t_shortcut_kylin.cpp ../src/app/ShortcutManager.cpp)
    find_package(Qt5 REQUIRED COMPONENTS DBus)
    target_include_directories(t_shortcut_kylin PRIVATE ../tests/fixtures ../src)
    target_compile_definitions(t_shortcut_kylin PRIVATE PIXIU_HAVE_KYSDK=1)
    target_link_libraries(t_shortcut_kylin PRIVATE Qt5::Widgets Qt5::Test Qt5::DBus)
    add_test(NAME shortcut_kylin_fixture COMMAND t_shortcut_kylin)
    set_tests_properties(shortcut_kylin_fixture PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_backend_events tests/t_backend_events.cpp)
    target_link_libraries(t_backend_events PRIVATE pixiu-management Qt5::Test)
    add_test(NAME backend_events COMMAND t_backend_events)
    set_tests_properties(backend_events PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_websocket_client ../tests/t_websocket_client.cpp)
    target_link_libraries(t_websocket_client PRIVATE pixiu-management Qt5::Test)
    add_test(NAME websocket_client COMMAND t_websocket_client)
    set_tests_properties(websocket_client PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_agent_evidence tests/t_agent_evidence.cpp)
    target_link_libraries(t_agent_evidence PRIVATE pixiu-management Qt5::Test)
    add_test(NAME agent_evidence COMMAND t_agent_evidence)
    # Run through the Python harness, which owns the backend and temporary data.
    add_executable(t_memory_edit_live tests/t_memory_edit_live.cpp)
    target_link_libraries(t_memory_edit_live PRIVATE pixiu-management Qt5::Test)
    add_executable(t_memory_workspace tests/t_memory_workspace.cpp)
    target_link_libraries(t_memory_workspace PRIVATE pixiu-management Qt5::Test)
    add_test(NAME memory_workspace COMMAND t_memory_workspace)
    set_tests_properties(memory_workspace PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_host_shortcut tests/t_host_shortcut.cpp)
    target_link_libraries(t_host_shortcut PRIVATE pixiu-management Qt5::Test)
    add_test(NAME host_shortcut COMMAND t_host_shortcut)
    set_tests_properties(host_shortcut PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_memory_update_transport tests/t_memory_update_transport.cpp)
    target_link_libraries(t_memory_update_transport PRIVATE pixiu-management Qt5::Test)
    add_test(NAME memory_update_transport COMMAND t_memory_update_transport)
    set_tests_properties(memory_update_transport PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    add_executable(t_product_dialogs ../tests/t_product_dialogs.cpp)
    target_link_libraries(t_product_dialogs PRIVATE pixiu-management Qt5::Test)
    target_compile_definitions(t_product_dialogs PRIVATE PIXIU_VERSION="${PIXIU_MANAGEMENT_VERSION}")
    add_test(NAME product_dialogs COMMAND t_product_dialogs)
    set_tests_properties(product_dialogs PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    foreach(upgrade_test IN ITEMS upgrade_utils upgrade_controller check_update_dialog http_backend contract_fixtures)
        add_executable(t_${upgrade_test} ../tests/t_${upgrade_test}.cpp)
        target_link_libraries(t_${upgrade_test} PRIVATE pixiu-management Qt5::Test)
        add_test(NAME ${upgrade_test} COMMAND t_${upgrade_test})
        set_tests_properties(${upgrade_test} PROPERTIES
            ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
            RESOURCE_LOCK pixiu_upgrade_temp_files)
    endforeach()
    foreach(isolation_test IN ITEMS upgrade_controller check_update_dialog)
        target_sources(t_${isolation_test} PRIVATE ../tests/IsolatedUpgradeTest.h)
    endforeach()
    add_test(NAME upgrade_controller_temp_isolation COMMAND bash
        "${CMAKE_CURRENT_SOURCE_DIR}/../tests/test-upgrade-temp-isolation.sh"
        $<TARGET_FILE:t_upgrade_controller> initialStateIsIdle)
    add_test(NAME check_update_dialog_temp_isolation COMMAND bash
        "${CMAKE_CURRENT_SOURCE_DIR}/../tests/test-upgrade-temp-isolation.sh"
        $<TARGET_FILE:t_check_update_dialog> upToDateDisablesUpgradeAndShowsLatest)
endif()
