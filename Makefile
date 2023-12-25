# Black magic, ref: https://pawamoy.github.io/posts/pass-makefile-args-as-typed-in-command-line/
# function that parses parameters from command line and allows us to get the content
args = $(foreach a,$($(subst -,_,$1)_args),$(if $(value $a),$a="$($a)"))
args_content = $(foreach a,$($(subst -,_,$1)_args),$(if $(value $a),"$($a)"))

# Black magic, part two, the reconing https://moonmilo1108.medium.com/bump-or-automate-your-version-number-in-makefile-9da466c857d9
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

# this is the list of parameters that given function will parse
commit_args = message
merge_args = message
major_args = message

build:
	docker build \
	--build-arg THING="value" \
	--tag ${IMAGE_NAME}\:${CUR_VERSION} \
	--tag ${IMAGE_NAME}\:latest \.

clean:
	docker image rm "${PWD##*/}"\:"${IMAGE_TAG}"
	docker image rm "${PWD##*/}"\:latest

commit:
	@echo "Commiting version $(VERSION)"
	git commit -a -m \"$(call args_content,$@)\"
	git tag ${VERSION}
	git push
	git push --tags

commit_change:
	@echo "modify image"
	git add . 
	git commit -m "modify image"
	git push

merge:
	@echo "Commiting version $(MERGE_VERSION)"
	git commit -a -m \"$(call args_content,$@)\"
	git tag ${MERGE_VERSION}
	git push
	git push --tags

major:
	@echo "Commiting version $(MAJOR_VERSION)"
	git commit -a -m \"$(call args_content,$@)\"
	git tag ${MAJOR_VERSION}
	git push
	git push --tags