FROM qgis/qgis:latest
ARG FUNCTION_DIR="/app"

RUN apt-get update && apt-get install -y python3-pip && pip3 install --upgrade pip && apt-get clean
RUN pip3 --no-cache-dir install boto3
RUN pip3 --no-cache-dir install urllib3
RUN apt-get clean
RUN pip cache purge


WORKDIR /
RUN mkdir -p ${FUNCTION_DIR}
RUN pip3 install --upgrade --target ${FUNCTION_DIR} awslambdaric

WORKDIR ${FUNCTION_DIR}
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie

ADD tiles.py ${FUNCTION_DIR}/.
COPY entry.sh ${FUNCTION_DIR}/.
RUN chmod 755 /usr/bin/aws-lambda-rie entry.sh
ENTRYPOINT [ "/app/entry.sh" ]
CMD [ "tiles.handler" ]