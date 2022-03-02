FROM localhost:5000/slew-villas
RUN pip install pika
COPY send_request.py receive.py /usr/bin/
COPY example.json /var/
RUN useradd user
RUN mkdir /etc/config
RUN chown user /etc/config
USER user
WORKDIR /usr/bin
CMD [ "/usr/bin/receive.py" ]
