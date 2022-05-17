all:
	docker build -t dpsim .
	docker tag dpsim localhost:5000/dpsim:worker
	docker push localhost:5000/dpsim:worker
