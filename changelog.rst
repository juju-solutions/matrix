Change Log
----------

0.10.0
^^^^^
Fri Apr 28 2017

* Added JaaS Support: pass in --cloud when deploying to JaaS
  controllers
* Added support for conjure-up spells: Juju-matrix automatically uses
  conjure-up to deploy if the bundle that it is deploying is a spell,
  and conjure-up is in your path.
* Removed most internal timeouts: these are best handled by tools
  calling juju-matrix.
* Fixed issue with juju-matrix hanging when the network connection
  breaks. Juju-matrix now exits with an error. (Removes much of the need
  for timeouts.)
* Chaos fixes
* Now uses python-libjuju 0.4.1
* Juju-matrix now exists with error code 101 on test failure, which helps
  to distinguish between Infrastructure issues (exit codes 1 or 200)
  and Test Failures.
* Juju-matrix respects "ha" flag in tests.yaml, which you can use to
  indicate that a bundle attempts to be a highly available one. By
  default, juju-matrix will only mark chaos runs as failures when run
  against an ha bundle.
* Renamed "glitch" to "chaos".
* Renamed to "juju-matrix". Can be run as a plugin "juju matrix", and
  is also namespaced for places like the snap store.
* Added snapcraft.yaml. You can now install juju-matrix as a snap!

0.9.0
^^^^^
Fri Mar 10 2017
* Incremented version, and generally prepared matrix for packaging and
  release.
