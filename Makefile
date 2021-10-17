SCRIPT = /usr/local/bin/occult
DIR = /opt/occult

.PHONY: venv
venv:
	if [ ! -d venv ]; then python3 -m venv venv; fi
	venv/bin/pip3 install -r requirements.txt

install-venv: _copy
	if [ ! -d ${DIR}/venv ]; then python3 -m venv ${DIR}/venv; fi
	${DIR}/venv/bin/pip3 install -r requirements.txt
	if [ -s ${SCRIPT} ]; then rm -vf ${SCRIPT}; fi
	echo '#!/bin/sh'                                            >  ${SCRIPT}
	echo "${DIR}/venv/bin/python3 ${DIR}/occult.py"   >> ${SCRIPT}
	chmod 555 ${SCRIPT}
	chown root ${SCRIPT}

tests: venv
	venv/bin/python3 -m unittest test_*.py

install: _copy
	if [ -f ${SCRIPT} ]; then rm -vf ${SCRIPT}; fi
	if [ ! -s ${SCRIPT} ]; then ln -s ${DIR}/occult.py ${SCRIPT}; fi

_copy:
	mkdir -p ${DIR}
	cp occult.py version.txt ${DIR}
	chmod 555 ${DIR}/occult.py
	chown root ${DIR}/occult.py

uninstall:
	rm -rf ${DIR}
	rm -f ${SCRIPT}