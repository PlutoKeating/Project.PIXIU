# PIXIU 发布流水线 Makefile 入口
ROOT := $(abspath ../..)
SCRIPTS := $(ROOT)/build/release/scripts
export PIXIU_ROOT := $(ROOT)

.PHONY: all clean governance test deb build-deb publish-staging publish-production

all: build-deb

clean:
	rm -rf $(ROOT)/build/release/out $(ROOT)/build/release/dist

governance:
	$(SCRIPTS)/verify-governance.sh
	bash $(ROOT)/build/release/tests/test-governance.sh
	bash $(ROOT)/build/release/tests/test-native-profile.sh
	bash $(ROOT)/build/release/tests/test-config-upgrade-policy.sh
	bash $(ROOT)/build/release/tests/test-agent-integration.sh

test:
	$(SCRIPTS)/test.sh

# 文档和对外交付使用的稳定短命令；保留 build-deb 作为显式内部目标。
deb: build-deb

build-deb:
	$(SCRIPTS)/build-deb.sh

publish-staging: build-deb
	$(SCRIPTS)/publish.sh staging

publish-production: build-deb
	$(SCRIPTS)/publish.sh production
