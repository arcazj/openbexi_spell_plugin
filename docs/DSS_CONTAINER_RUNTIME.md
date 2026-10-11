# Existing DSS image runtime evidence

The earlier Docker startup stall no longer reproduces on this host. The existing
v0.1 DSS image, recorded by exact image digest in
[DSS_CONTAINER_RUNTIME.json](DSS_CONTAINER_RUNTIME.json), passed two probes:
a Python startup and the actual deterministic DSS command workflow.

The workflow ran as UID 10003 with Docker networking disabled. Its own HTTP and
binary TCP servers communicated on container loopback. It read and verified TM1,
executed CMD1 once, checked the payload state change and independently decoded
TRANSPORT, LOADING, RELEASE, ACKNOWLEDGEMENT and ONBOARD_EXECUTION packets. Both
server workers joined and the database closed. The reproducible probe is
[scripts/qualify_dss_container.py](../scripts/qualify_dss_container.py).

The two exact test containers exited with status zero and were removed after
evidence capture. The current image and host DSS/session services were retained.
No Docker reset, unrelated container/volume deletion or image removal was needed.

This establishes an in-container bounded v0.1 workflow. It does not establish
host-published HTTP access: the current local fixture deliberately binds to
container loopback. Explicit container binding/publishing and the original driver
families remain later release work. The v0.6 distribution gate stays open.
