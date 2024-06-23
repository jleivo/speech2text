# Black magic, https://moonmilo1108.medium.com/bump-or-automate-your-version-number-in-makefile-9da466c857d9
# Automatic minor version numbering

ifeq ($(VERSION),)
     VERSION:=$(shell git describe --tags --abbrev=0 | awk -F . '{OFS="."; $$NF+=1; print}')
endif

ifeq ($(MERGE_VERSION),)
     MERGE_VERSION:=$(shell git describe --tags --abbrev=0 | awk -F . '{$$2=$$2+1; print $$1 "." $$2 ".0"}')
endif

ifeq ($(MAJOR_VERSION),)
     MAJOR_VERSION:=$(shell git describe --tags --abbrev=0 | awk -F . '{OFS="."; $$1+=1; print $$1 ".0.0"}')
endif

ifeq ($(CUR_VERSION),)
     CUR_VERSION:=$(shell git describe --tags --abbrev=0)
endif
##### Makefile specific #######

# Normal stuff..
SHELL := /bin/bash
IMAGE_NAME := $(shell basename ${PWD})
REPO_NAME := "docker.intra.leivo"
BUILD_NUMBER := $(shell git rev-parse --short HEAD)

build:
	docker build \
	--tag ${IMAGE_NAME}\:${CUR_VERSION} \
	--tag ${IMAGE_NAME}\:latest \.

test_build:
	docker build \
	--tag ${IMAGE_NAME}\:${BUILD_NUMBER} \
	--tag ${IMAGE_NAME}\:test \.

test_push:
	docker tag \
	${IMAGE_NAME}\:${BUILD_NUMBER} \
	$(REPO_NAME)/$(IMAGE_NAME)\:${BUILD_NUMBER}

	docker tag \
	${IMAGE_NAME}\:${BUILD_NUMBER} \
	$(REPO_NAME)/$(IMAGE_NAME)\:test

	docker push \
	$(REPO_NAME)/$(IMAGE_NAME)\:${BUILD_NUMBER}

	docker push \
	$(REPO_NAME)/$(IMAGE_NAME)\:test


clean:
	docker image rm "${IMAGE_NAME}"\:"${CUR_VERSION}"
	docker image rm "${IMAGE_NAME}"\:test

release:
	@echo "Creating version $(VERSION)"
	git tag ${VERSION}
	git push
	git push --tags

minor_release:
	git tag ${MERGE_VERSION}
	git push
	git push --tags

major_release:
	git tag ${MAJOR_VERSION}
	git push
	git push --tags
