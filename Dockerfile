FROM qgis/qgis:latest
ARG FUNCTION_DIR="/app"
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY
ARG AWS_REGION
ARG TEST='Test'
ENV AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
ENV AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
ENV AWS_REGION=$AWS_REGION

RUN apt-get update && apt-get install -y python3-pip && pip3 install --upgrade pip && apt-get clean
RUN pip3 --no-cache-dir install boto3
RUN pip3 --no-cache-dir install urllib3
RUN apt-get clean
RUN pip cache purge

WORKDIR /
RUN mkdir -p ${FUNCTION_DIR}
RUN mkdir -p /root/.aws
RUN touch /root/.aws/credentials
RUN echo '[default]' > /root/.aws/credentials
RUN echo 'AWS_ACCESS_KEY_ID='$AWS_ACCESS_KEY_ID >> /root/.aws/credentials
RUN echo 'AWS_SECRET_ACCESS_KEY='$AWS_SECRET_ACCESS_KEY >> /root/.aws/credentials
RUN echo 'AWS_REGION='$AWS_REGION >> /root/.aws/credentials
RUN pip3 install --upgrade --target ${FUNCTION_DIR} awslambdaric

WORKDIR ${FUNCTION_DIR}
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie

ADD tiles.py ${FUNCTION_DIR}/.
COPY entry.sh ${FUNCTION_DIR}/.
RUN chmod 755 /usr/bin/aws-lambda-rie entry.sh
ENTRYPOINT [ "/app/entry.sh" ]
CMD [ "tiles.handler" ]