# Changelog

## [2.0.1](https://github.com/soerenschneider/occult/compare/v2.0.0...v2.0.1) (2023-06-22)


### Bug Fixes

* be more consistent and expect cmd as string ([d1a19c4](https://github.com/soerenschneider/occult/commit/d1a19c4369a4e641045eab40e7bb2dfc9c8dde20))
* run all post_hooks even on failure of an earlier one ([67e9eb8](https://github.com/soerenschneider/occult/commit/67e9eb87b8129df5009f9a6e618e97a49037e60b))

## [2.0.0](https://github.com/soerenschneider/occult/compare/v1.6.0...v2.0.0) (2023-06-19)


### ⚠ BREAKING CHANGES

* change type of cmd and post_hooks

### Code Refactoring

* change type of cmd and post_hooks ([bc59732](https://github.com/soerenschneider/occult/commit/bc59732bf8eaa706cd2fec4647dc05c9b80b6c32))

## [1.6.0](https://github.com/soerenschneider/occult/compare/v1.5.2...v1.6.0) (2022-06-21)


### Features

* Allow running multiple post_hooks ([2329ebc](https://github.com/soerenschneider/occult/commit/2329ebc9b8f40e8dba87e36ea765ef6b344eb21d))

### [1.5.2](https://www.github.com/soerenschneider/occult/compare/v1.5.1...v1.5.2) (2022-02-24)


### Bug Fixes

* Catch errors when building auth method ([7e948aa](https://www.github.com/soerenschneider/occult/commit/7e948aa5ea7e467c18ae6bc554fa69b6896e8e84))

### [1.5.1](https://www.github.com/soerenschneider/occult/compare/v1.5.0...v1.5.1) (2022-01-23)


### Miscellaneous Chores

* release 1.5.1 ([2194dd4](https://www.github.com/soerenschneider/occult/commit/2194dd41793e4d6d945c28d4ea1775353ffd4633))

## [1.5.0](https://www.github.com/soerenschneider/occult/compare/v1.4.0...v1.5.0) (2022-01-22)


### Features

* complete rewrite ([4cbafbd](https://www.github.com/soerenschneider/occult/commit/4cbafbdf9985a6421fe3ece7818292e03be69f09))

## [1.4.0](https://www.github.com/soerenschneider/occult/compare/v1.3.0...v1.4.0) (2021-10-20)


### Features

* try to renew token ([f9778cf](https://www.github.com/soerenschneider/occult/commit/f9778cf85c38d8aa127cf76b93f4e97572103e9d))

## [1.3.0](https://www.github.com/soerenschneider/occult/compare/v1.2.2...v1.3.0) (2021-10-17)


### Features

* Add possibility for different profiles ([942f036](https://www.github.com/soerenschneider/occult/commit/942f03684af4efd887c8560e05f5b82b83f08bd6))


### Bug Fixes

* Replace relative expiry value with absolute value ([d0ad91e](https://www.github.com/soerenschneider/occult/commit/d0ad91eaaf2f3868a292f08363b61e94246d1ce0))

### [1.2.2](https://www.github.com/soerenschneider/occult/compare/v1.2.1...v1.2.2) (2021-10-05)


### Bug Fixes

* Fix invalid metric format ([a8ee377](https://www.github.com/soerenschneider/occult/commit/a8ee377361bc5f8d6ec019841877a74b189536aa))

### [1.2.1](https://www.github.com/soerenschneider/occult/compare/v1.2.0...v1.2.1) (2021-09-22)


### Bug Fixes

* ignore cmd output ([972d65b](https://www.github.com/soerenschneider/occult/commit/972d65b46407f19796fc2ca64effb7178faf1262))

## [1.2.0](https://www.github.com/soerenschneider/occult/compare/v1.1.1...v1.2.0) (2021-09-06)


### Features

* Check file permissions and panic if too liberal ([328d17e](https://www.github.com/soerenschneider/occult/commit/328d17ef8ddb9e1d5c36f800cfe68287faf94c41))

### [1.1.1](https://www.github.com/soerenschneider/occult/compare/v1.1.0...v1.1.1) (2021-09-04)


### Bug Fixes

* wait for process to complete ([c2464cf](https://www.github.com/soerenschneider/occult/commit/c2464cf1511ac34293cea955b854cea1179f72a0))

## [1.1.0](https://www.github.com/soerenschneider/occult/compare/v1.0.0...v1.1.0) (2021-09-04)


### Features

* ability for token reflection regarding ttl ([28d8d12](https://www.github.com/soerenschneider/occult/commit/28d8d12ba2c638496ba46ff5a6e6cf8fca77f470))


### Bug Fixes

* Fix post_hooks ([38c168e](https://www.github.com/soerenschneider/occult/commit/38c168e827bcead8054c2533e5f440f3b1eab71a))

## 1.0.0 (2021-09-03)


### Features

* Enable specifying json secret path ([fed7261](https://www.github.com/soerenschneider/occult/commit/fed72618f60272d8d62ac4286ca0b9dfd05f9cdb))
