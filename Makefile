.PHONY: venv
venv:
	if [ ! -d venv ]; then python3 -m venv venv; fi
	venv/bin/pip3 install -r requirements.txt

install:
	mkdir -p /opt/occult
	if [ ! -d /opt/occult/venv ]; then python3 -m venv /opt/occult/venv; fi
	/opt/occult/venv/bin/pip3 install -r requirements.txt
	cp occult.py /opt/occult
	chmod 555 /opt/occult/occult.py
	if [ ! -s /usr/local/bin/occult ]; then ln -s /opt/occult/occult.py /usr/local/bin/occult; fi