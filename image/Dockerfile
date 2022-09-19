
FROM sogno/dpsim:dev

RUN yum -y install python3-pip
RUN pip3 install pika build

RUN git clone https://github.com/sogno-platform/dpsim /dpsim
RUN mkdir /dpsim/build && cd /dpsim/build
WORKDIR /dpsim
RUN python3 -m build --wheel
RUN python3 -m pip install ./dist/dpsim*

WORKDIR /dpsim/build
RUN cmake -DWITH_PYBIND=ON -DDPSIM_BUILD_EXAMPLES=OFF -DGET_GRID_DATA=OFF .. && make
RUN cp /dpsim/build/dpsimpyvillas*.so /usr/local/lib64/python3.9/site-packages/

WORKDIR /dpsim

RUN pip install pika
COPY send_request.py receive.py /usr/bin/
RUN useradd user
RUN mkdir -p /etc/config/model
RUN mkdir -p /etc/config/loadprofile
RUN chown -R user /etc/config
RUN mkdir -p /run
RUN chown user /run
USER user

WORKDIR /run
CMD [ "/usr/bin/receive.py" ]
