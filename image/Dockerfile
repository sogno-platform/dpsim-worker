
FROM sogno/dpsim:latest

# install dpsimpy
RUN rm -rf /dpsim/build && mkdir /dpsim/build
WORKDIR /dpsim
RUN python3 -m build --wheel
RUN python3 -m pip install ./dist/dpsim*

RUN pip install pika
COPY send_request.py receive.py /usr/bin/
RUN useradd user
RUN mkdir -p /etc/config/model
RUN chown -R user /etc/config
RUN mkdir -p /run
RUN chown user /run
USER user
WORKDIR /run
CMD [ "/usr/bin/receive.py" ]
