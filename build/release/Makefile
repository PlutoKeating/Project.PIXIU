# PIXIU 发布流水线 Makefile 入口
ROOT := $(abspath ../..)
SCRIPTS := $(ROOT)/build/release/scripts
export PIXIU_ROOT := $(ROOT)

.PHONY: all clean governance test build-deb publish-staging publish-production

all: build-deb

clean:
	rm -rf $(ROOT)/build/release/out $(ROOT)/build/release/dist

governance:
	$(SCRIPTS)/verify-governance.sh
	bash $(ROOT)/build/release/tests/test-governance.sh
	bash $(ROOT)/build/release/tests/test-native-profile.sh

test:
	$(SCRIPTS)/test.sh

build-deb:
	$(SCRIPTS)/build-deb.sh

publish-staging: build-deb
	$(SCRIPTS)/publish.sh staging

publish-production: build-deb
	$(SCRIPTS)/publish.sh production
