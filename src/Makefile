PROJECT := CPP_AUTOTEST
PACKAGE := autotest
EGG_INFO := $(subst -,_,$(PACKAGE)).egg-info

ifeq ($(OS),Windows_NT)
BIN := Scripts
INCLUDE := Include
LIB := Lib
MAN := man
EXE := .exe
else
BIN := bin
INCLUDE := include
LIB := lib
MAN := man
endif

WD := $(shell pwd)
CACHE := $(WD)/.cache
PYTHON := $(WD)/$(BIN)/python$(EXE)
EASY_INSTALL := $(WD)/$(BIN)/easy_install$(EXE)
PIP := $(WD)/$(BIN)/pip$(EXE)
EPYDOC := $(WD)/$(BIN)/epydoc$(EXE)
PEP8 := $(WD)/$(BIN)/pep8$(EXE)
PYLINT := $(WD)/$(BIN)/pylint$(EXE)
NOSE := $(WD)/$(BIN)/nosetests$(EXE)

# Fake Targets for the Build System ##########################################

.PHONY: all
all: install

.PHONY: install
install:
	@echo
	@echo ERROR: to install $(PROJECT) use "'make setup'"

# System Installation ########################################################

.PHONY: setup
ifeq ($(OS),Windows_NT)
setup:
	@echo
	@echo ERROR: to install $(PROJECT) use "'./make.bat setup'"
else
setup:
	${MAKE} setuptools || ${MAKE} network
endif

setuptools:
	# Install setuptools
	sudo sh lib/setuptools-0.6c11-py2.6.egg
	# Run distribution script
	sudo python setup.py install
	# Delete temporary files
	sudo $(MAKE) .clean-dist
	# Generate documentation
	/usr/local/bin/epydoc -qq --config setup.cfg

network:
	# Check for network access
	if ping example.com -c 1; \
	then :; else \
		echo; \
		echo \#############################################################################; \
		echo \# ERROR: no network connection detected, connect to the network and try again; \
		echo \#############################################################################; \
		echo; \
		exit 1; \
	fi
	# Check for apt-get proxy access
	if sudo apt-get --yes --force-yes --reinstall install curl;	\
	then :; else \
		echo; \
		echo \############################################################################; \
		echo \# ERROR: no proxy access detected, update your proxy settings and try again:; \
		echo \# http://osqa.ag.na.jci.com/questions/676; \
		echo \############################################################################; \
		echo; \
		exit 1; \
	fi
	# An unknown error has occured
	echo; \
	echo \##########################################################################; \
	echo \# Network connectivity is good, but ${CPP_NAME} did not install correctly; \
	echo \##########################################################################; \
	echo; \
	exit 1; \

opera: opera
	# Optional installer for Opera
	echo "deb http://deb.opera.com/opera/ stable non-free" | sudo tee /etc/apt/sources.list.d/opera.list
	wget -qO - http://deb.opera.com/archive.key | sudo apt-key add -
	sudo apt-get update
	sudo apt-get install debian-archive-keyring
	sudo apt-get install opera --yes --force-yes

# Installation ###############################################################

.PHONY: develop
develop: .env depends $(EGG_INFO)
$(EGG_INFO):
	$(PYTHON) setup.py develop

.PHONY: .env
.env: $(PYTHON)
$(PYTHON):
	virtualenv .

.PHONY: depends
depends: .env .depends
.depends:
	$(PIP) install nose pep8 pylint --download-cache=$(CACHE)
	$(MAKE) .depends-os
	$(MAKE) .coverage
	touch .depends  # flag to indicate dependencies are installed

.PHONY: .depends-os
ifeq ($(OS),Windows_NT)
.depends-os:
	$(EASY_INSTALL) lib/autopy-0.51.win32-py2.7.exe
	$(EASY_INSTALL) lib/epydoc-3.0.1.win32.exe
	$(EASY_INSTALL) lib/PyUSB-1.6.win32-py2.7.exe
else
.depends-os:
	$(PIP) install epydoc --download-cache=$(CACHE)
endif

.PHONY: .coverage
# issue: coverage results are incorrect in Linux
# tracker: https://bitbucket.org/ned/coveragepy/issue/164
# workaround: install the latest code from bitbucket.org until "coverage>3.6"
ifeq ($(shell uname),Linux)
.coverage: .env $(CACHE)/coveragepy
	cd $(CACHE)/coveragepy; \
	$(PIP) install --requirement requirements.txt --download-cache=$(CACHE); \
	$(PYTHON) setup.py install
$(CACHE)/coveragepy:
	cd $(CACHE); hg clone https://bitbucket.org/ned/coveragepy
else
.coverage: .env
	$(PIP) install coverage --download-cache=$(CACHE)
endif

# Documentation ##############################################################

.PHONY: epydoc
# issue: epydoc does not install a working CLI on Windows
# tracker: http://sourceforge.net/p/epydoc/bugs/345
# workaround: using epydoc.cmd from the system site-packages
ifeq ($(OS),Windows_NT)
epydoc: depends
	C:\\Python27\\python.exe C:\\Python27\\Scripts\\epydoc.py -v --config setup.cfg
else
epydoc: depends
	$(EPYDOC) -v --config setup.cfg
endif

.PHONY: doc
doc: epydoc
	cd ../documentation; ./show_apidocs.cmd

# Static Analysis ############################################################

.PHONY: pep8
pep8: depends
	$(PEP8) --ignore=E501 $(PACKAGE)

.PHONY: pylint
pylint: depends
	$(PYLINT) $(PACKAGE) --include-ids yes --reports no --disable W0142,W0511,I0011,R,C

.PHONY: check
check: epydoc pep8 pylint

# Testing ####################################################################

.PHONY: nose
nose: depends develop
	$(NOSE)

.PHONY: test
test: depends develop
	$(NOSE) --with-doctest

# Cleanup ####################################################################

.PHONY: .clean-env
.clean-env:
	rm -rf .Python $(BIN) $(INCLUDE) $(MAN)
	rm -rf $(LIB)/*.py $(LIB)/*.txt
	rm -rf $(LIB)/distutils
	rm -rf $(LIB)/encodings
	rm -rf $(LIB)/site-packages
	rm -rf $(LIB)/python2*
	rm -rf .depends
	rm -rf local

.PHONY: .clean-dist
.clean-dist:
	rm -rf build dist *.egg-info
	rm -rf lib/*/build lib/*/dist lib/*/*.egg-info

.PHONY: clean
clean: .clean-env .clean-dist
	rm -rf */*/*/*/*/cover
	rm -rf ../*.pyc
	rm -rf ../*/*.pyc
	rm -rf ../*/*/*.pyc
	rm -rf ../*/*/*/*.log
	rm -rf ../*/*/*/*.pyc
	rm -rf ../*/*/*/*/*.pyc
	rm -rf ../*/*/*/*/*/*.pyc
	rm -rf ../*/*/*/*/*/*/*.pyc
	rm -rf ../documentation/apidocs
	rm -rf .coverage
	rm -rf cover