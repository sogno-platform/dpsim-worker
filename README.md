# dpsim-worker

## build
cd image && make & cd ..

## install
helm install dpsim-worker .

## test
kubectl run -i --rm send-test-request --image=localhost:5000/dpsim-worker --restart=Never -- send_request.py

## validate
kubectl logs $(kubectl get pods -o name | grep "dpsim-worker")
