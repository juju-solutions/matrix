Matrix
======

Welcome to the real world.

This is a test engine designed to validate proper function of real-world
software solutions under a variety of adverse conditions. While this system can
run in a way very similar to bundletester this engine is designed to a
different model. The idea here is to bring up a running deployment, set of a
pattern of application level tests and ensure that the system functions after
operations modelled with Juju are performed. In addition the system supports
large scale failure injection such a removal of units or machines while tests
are executing. It is because of this async nature that the engine is written on
a fresh codebase.

Every effort should be made by the engine to correlate mutations to failure
states and produce helpful logs.

High level Design
------------------

Tests are run by an async engine driven by a simple rule engine. The reason to
do things in this way is so we can express the high level test plan in terms of
rules and states (similar to reactive and layer-cake).

    tests:
    - name: Traffic
      description: Traffic in the face of Chaos
      rules:
        - do:
            action: deploy
            version: current
        - do: test_traffic
          until: chaos.done
          after: deploy
        - do:
            action: chaos
          while: test_traffic
        - do:
            action: health
            periodic: 5
          until: chaos.done

Given this YAML test definition fragment the intention here is as follows.
Define a test relative to a bundle. Deploy that bundle, this will set a state
triggering the next rule and invoking a traffic generating test. The traffic
generating test should be run "until" a state is set (chaos.done) and may be
invoked more than once by the engine. While the engine is running the traffic
suite a state (test_traffic based on test name) will be set. This allows
triggering of the "while" rule which launches another task (chaos) on the
current deployment. When that task has done what it deems sufficient it can
exit, which will stop the execution of the traffic test. 

Rules are evaluated continuously until the test completes and may run in
parallel. Excessive used of parallelism can make failure analysis more
complicated for the user however.

For a system like this to function we must continuously assert the health of
the running bundle. This means there is a implicit task checking agent/workload
health after every state change in the system. State in this case means states
set by rules and transitions between rules. As Juju grows a real health system
we'd naturally extend to depend on that.


Tasks
-----

The system includes a number of built in tasks that are resolved from any do
clause if no matching file is found in the tests directory. Currently these
tasks are

    deploy
        version: *current* | prev

    upgrade:
        version: *current*

    chaos:
        applications: *all* | [by_name]

Chaos internally might have a number of named components and mutation events
that can be used to perturb the model. Configuration there of TBD.


Plugins
--------

If there is no binary on the path of a give do:action: name then the action
will attempt to load a Python object via a dotted import path. The last object
should be callable and can expect handler(context, rule) as its signature. The
context object is the rules Context object and rule is the current Rule
instance. The object should return a boolean indicating if the rule is
complete. If the task is designed to run via an 'until' condition it will be
marked as complete after its task has been cancelled.

Quick Start
-----------

    clone https://github.com/juju-solutions/matrix.git
    cd matrix/
    tox
    .tox/py35/bin/matrix tests/test_prog

When you update the branch remove the .tox directory and re-run tox

    git pull
    rm -rf ./tox
    tox
    .tox/py35/bin/matrix tests/test_prog
