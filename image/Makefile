
MINIKUBE_IP:=$(shell minikube ip)
all:
	docker build -t dpsim:worker .
	docker tag dpsim:worker ${MINIKUBE_IP}:5000/dpsim:worker
	docker push ${MINIKUBE_IP}:5000/dpsim:worker
