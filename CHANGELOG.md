# [0.4.1] - (2020-05-04)


### Features
* **versioneer:** add versioneer for better version naming ([f723699](https://github.com/chime-experiment/chimedb/commit/f723699e73f56f6b7f1e09c7560ed76312ebaff3))



# [0.4.0] - (2020-01-10)


### Bug Fixes

* **test:** properly mock os.environ ([#13](https://github.com/chime-experiment/chimedb/issues/13)) ([2f52958](https://github.com/chime-experiment/chimedb/commit/2f529584b5c422668a8e098eb49b7ef18308a5ad))


### Features

* **connectdb:** turn on test-safe mode via environment ([#11](https://github.com/chime-experiment/chimedb/issues/11)) ([cfa61c9](https://github.com/chime-experiment/chimedb/commit/cfa61c93eb007eec01d7603f5e00689c21a686e1))
* **core:** add atomic decorator/context manager ([#12](https://github.com/chime-experiment/chimedb/issues/12)) ([fc50211](https://github.com/chime-experiment/chimedb/commit/fc502111831818b824dcfb1728dfc5de0a52923b))
* **orm:** backport a better EnumField from alpenhorn2 ([#14](https://github.com/chime-experiment/chimedb/issues/14)) ([90b63e6](https://github.com/chime-experiment/chimedb/commit/90b63e61cd47441b0f5db4099fee377a4ae1d0bd))



# [0.3.1] - (2019-09-27)


### Bug Fixes

* **connectdb:** Make db_type case-insensitive. ([2265b26](https://github.com/chime-experiment/chimedb/commit/2265b26aa2ed4bc827a554e1f851bf909a477655)), closes [#8](https://github.com/chime-experiment/chimedb/issues/8)
* **core:** delete obsolete "util" module  ([#7](https://github.com/chime-experiment/chimedb/issues/7)) ([65b9161](https://github.com/chime-experiment/chimedb/commit/65b91617bd8109a2857822c3cc8c73c35e4360b4))


### Features

* **core:** test-safe mode ([#10](https://github.com/chime-experiment/chimedb/issues/10)) ([388dec1](https://github.com/chime-experiment/chimedb/commit/388dec15ae9651a100a774c625737df013e9aafc))



# [0.3.0] - (2019-09-27)


### Bug Fixes

* **connectdb:** fix switching between ro and rw connectors ([#6](https://github.com/chime-experiment/chimedb/issues/6)) ([0d0be4f](https://github.com/chime-experiment/chimedb/commit/0d0be4f4c4e38b26570b69b53c653a6bfb674025))


### Features

* **orm:** make JSONDictField use LONGTEXT fields ([5944fee](https://github.com/chime-experiment/chimedb/commit/5944fee371353d434b9315f631f0ef2577501bb1))



# [0.2.0] - (2019-09-18)


### Bug Fixes

* **create_tables:** Don't try to import chimedb.setup ([54145a2](https://github.com/chime-experiment/chimedb/commit/54145a29574199074715c132a2b20a3b5357a46f))


### Features

* add create_tables function for finding and creating chimedb tables ([#3](https://github.com/chime-experiment/chimedb/issues/3)) ([674a6a1](https://github.com/chime-experiment/chimedb/commit/674a6a1adca24044a504d4aa5161baf0dbd7b6d9))



# [0.2.0] - (2019-09-18)


### Features

* **connectdb:** Add chimedb.core.close() ([3f519cf](https://github.com/chime-experiment/chimedb/commit/3f519cfc52ca6ec72b0b4b7d6b92bbb047ebb388))
