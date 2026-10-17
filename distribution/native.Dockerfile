# Each --no-cache invocation starts with no source, object, or native output tree.
ARG TOOLCHAIN_IMAGE
FROM ${TOOLCHAIN_IMAGE} AS native
ENV SOURCE_DATE_EPOCH=1791676800 PYTHONHASHSEED=0 TZ=UTC LC_ALL=C.UTF-8
COPY docs/reference/SPELL2.6.10-src.zip /input/SPELL2.6.10-src.zip
COPY source_port/native /input/native
COPY source_port/native_patches.py source_port/native_manifest.py source_port/native_build.py /input/
COPY source_port/integrated_patches.py source_port/patches.py source_port/data_files_native_patches.py source_port/data_files_patches.py source_port/dta_native_patches.py source_port/dta_time_patches.py source_port/flow_patches.py source_port/flow_analyze.py source_port/obs_patches.py source_port/ui_native_patches.py /input/
COPY source_port/cmd_patches.py source_port/dta_ipc_patches.py /input/
COPY source_port/scheduler_patches.py source_port/resource_patches.py source_port/limit_patches.py source_port/database_import_patches.py source_port/notification_patches.py source_port/value_units_patches.py source_port/user_database_patches.py /input/
COPY source_port/scdb_patches.py source_port/timing_patches.py source_port/checkpoint_error_patches.py source_port/send_verify_patches.py /input/
COPY source_port/checkpoint_identity_patches.py source_port/checkpoint_context_patches.py /input/
COPY source_port/shutdown_pause_patches.py /input/
COPY source_port/child_lifecycle_patches.py source_port/prompt_timeout_patches.py /input/
COPY source_port/prompt_control_patches.py /input/
COPY source_port/prompt_startup_patches.py /input/
COPY source_port/proc_dictionary_patches.py source_port/wait_interrupt_patches.py /input/
COPY source_port/database_values_patches.py /input/
COPY source_port/ipc_mailbox_patches.py /input/
COPY source_port/context_snapshot_patches.py /input/
COPY source_port/legacy_compare_patches.py source_port/legacy_compare_syntax.py /input/
COPY source_port/rng_patches.py source_port/rng_state_patches.py /input/
COPY source_port/display_patches.py source_port/command_feature_patches.py source_port/command_catalog_patches.py source_port/command_group_patches.py /input/
COPY source_port/native-build.Dockerfile source_port/native-build.Dockerfile.dockerignore /input/
COPY source_port/database_format_patches.py source_port/limit_feature_patches.py source_port/manoeuvre_database_patches.py source_port/memory_feature_patches.py source_port/memory_ranging_patches.py source_port/procedure_library_patches.py source_port/ranging_complete_patches.py source_port/ranging_reopen_patches.py source_port/send_complete_patches.py source_port/telemetry_feature_patches.py /input/
COPY source_port/prompt_complete_patches.py source_port/event_text_patches.py source_port/memory_command_results_patches.py /input/
COPY source_port/prompt_empty_option_patches.py source_port/event_empty_native_patches.py /input/
RUN python /input/native_build.py --integrated
COPY source_port/experiments /experiment
RUN python /experiment/build_probe.py
COPY source_port/executor-build.lock source_port/executor_build.py source_port/qualify_executor.py source_port/patches.py /executor/
COPY source_port/integrated_patches.py source_port/native_patches.py source_port/data_files_native_patches.py source_port/data_files_patches.py source_port/dta_native_patches.py source_port/dta_time_patches.py source_port/flow_patches.py source_port/flow_analyze.py source_port/obs_patches.py source_port/ui_native_patches.py /executor/
COPY source_port/cmd_patches.py source_port/dta_ipc_patches.py /executor/
COPY source_port/scheduler_patches.py source_port/resource_patches.py source_port/limit_patches.py source_port/database_import_patches.py source_port/notification_patches.py source_port/value_units_patches.py source_port/user_database_patches.py /executor/
COPY source_port/scdb_patches.py source_port/timing_patches.py source_port/checkpoint_error_patches.py source_port/send_verify_patches.py /executor/
COPY source_port/checkpoint_identity_patches.py source_port/checkpoint_context_patches.py /executor/
COPY source_port/shutdown_pause_patches.py /executor/
COPY source_port/child_lifecycle_patches.py source_port/prompt_timeout_patches.py /executor/
COPY source_port/prompt_control_patches.py /executor/
COPY source_port/prompt_startup_patches.py /executor/
COPY source_port/proc_dictionary_patches.py source_port/wait_interrupt_patches.py /executor/
COPY source_port/database_values_patches.py /executor/
COPY source_port/ipc_mailbox_patches.py /executor/
COPY source_port/context_snapshot_patches.py /executor/
COPY source_port/legacy_compare_patches.py source_port/legacy_compare_syntax.py /executor/
COPY source_port/rng_patches.py source_port/rng_state_patches.py /executor/
COPY source_port/display_patches.py source_port/command_feature_patches.py source_port/command_catalog_patches.py source_port/command_group_patches.py /executor/
COPY source_port/executor-build.Dockerfile source_port/executor-build.Dockerfile.dockerignore /executor/
COPY source_port/database_format_patches.py source_port/limit_feature_patches.py source_port/manoeuvre_database_patches.py source_port/memory_feature_patches.py source_port/memory_ranging_patches.py source_port/procedure_library_patches.py source_port/ranging_complete_patches.py source_port/ranging_reopen_patches.py source_port/send_complete_patches.py source_port/telemetry_feature_patches.py /executor/
COPY source_port/prompt_complete_patches.py source_port/event_text_patches.py source_port/memory_command_results_patches.py /executor/
COPY source_port/prompt_empty_option_patches.py source_port/event_empty_native_patches.py /executor/
RUN python /executor/executor_build.py --integrated
COPY source_port/context_build.py source_port/context_peer.cpp source_port/qualify_context.py source_port/qualify_process.cpp source_port/server_peer.cpp source_port/qualify_service_bindings.cpp source_port/qualify_service_bindings.py source_port/controller_peer.cpp source_port/controller_fixtures.py source_port/service_recovery_peer.cpp source_port/service_recovery_fixtures.py source_port/cif_fixtures.py source_port/qualify_ipc_ownership.cpp source_port/qualify_context_ownership.cpp source_port/live_reconnect_peer.cpp source_port/live_reconnect_fixtures.py /context/
COPY source_port/context-build.Dockerfile source_port/context-build.Dockerfile.dockerignore /context/
RUN python /context/context_build.py
COPY source_port /recipe/source_port
COPY distribution /recipe/distribution
COPY docs/reference/SPELL2.6.10-src.zip /recipe/docs/reference/SPELL2.6.10-src.zip
RUN c++ -std=c++17 -g -pthread -fsanitize=address,undefined -I/source/include -I/usr/local/include/python3.13 /recipe/source_port/installed_peer.cpp -L/out -lspell_executor313 -Wl,-rpath,'$ORIGIN' -L/usr/local/lib -lpython3.13 -o /out/installed_peer
RUN python /recipe/source_port/package_native.py --integrated --output /package
RUN python /recipe/distribution/stable_wheel.py --package /package --output /stable

FROM ${TOOLCHAIN_IMAGE} AS installed
COPY --from=native /stable/wheels /distribution
COPY --from=native /out/installed_peer /qualification-input/installed_peer
COPY source_port/qualify_package.py /qualification-input/qualify_package.py
RUN python -I /qualification-input/qualify_package.py

FROM scratch AS evidence
COPY --from=native /out /native
COPY --from=native /stable /distribution
COPY --from=native /package/package-result.json /legacy-package-result.json
COPY --from=native /recipe/docs/NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json /native-qualification.json
COPY --from=native /toolchain /toolchain
COPY --from=installed /qualification /installed
