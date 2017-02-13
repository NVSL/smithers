VERSION_NAME ?= testing
DEP_DIRECTORY ?= deploy_local

default:
	npm install
	DEPLOY_DIRECTORY=$(DEP_DIRECTORY) grunt build_local

deploy-local: default

.PHONY: clean realclean
clean:
	if ! [ -d node_modules ]; then npm install; fi
	DEPLOY_DIRECTORY=$(DEP_DIRECTORY) grunt clean:tidy

realclean:
	DEPLOY_DIRECTORY=$(DEP_DIRECTORY) grunt clean

run:
	(cd $(DEP_DIRECTORY); yes y | dev_appserver.py --log_level info .)

test:
	true

.PHONY: deploy
deploy:
	mkdir -p deploy
	DEPLOY_DIRECTORY=deploy grunt build_deploy
	appcfg.py -V release update deploy/app.yaml
	appcfg.py update_indexes deploy

.PHONY: deploy-test
deploy-test:
	mkdir -p deploy-test
	DEPLOY_DIRECTORY=deploy-test grunt build_deploy
	appcfg.py -V testing update deploy-test/app.yaml
	appcfg.py update_indexes deploy-test
