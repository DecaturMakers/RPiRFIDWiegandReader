install:
	pip3 install --force-reinstall --upgrade .
	install -m 644 rfidclient.service /etc/systemd/system
	install -m 644 rfid-prometheus.service /etc/systemd/system
	[ -f /etc/default/rfidclient ] || install -m 644 example.env /etc/default/rfidclient
	systemctl daemon-reload || true
	systemctl enable rfidclient.service
	systemctl enable rfid-prometheus.service
