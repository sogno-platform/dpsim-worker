# dpsim-worker

### This is a work in progress. A working prototype can be run using [the example deployments project](https://github.com/sogno-platform/example-deployments).

## build
cd image && make & cd ..

## install
helm install dpsim-worker .

## test
kubectl run -i --rm send-test-request --image=sogno/dpsim:worker --restart=Never -- send_request.py

## validate
kubectl logs $(kubectl get pods -o name | grep "dpsim-worker")

