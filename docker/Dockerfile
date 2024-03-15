FROM python:3.13.0a4-alpine

RUN addgroup -g 1234 -S synchro && adduser -u 1234 -G synchro -h /home/synchro -D synchro
USER synchro
WORKDIR /home/synchro

# Copy function code
COPY src ./src

RUN pip install -r ./src/requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "./src/main.py" ]
ENTRYPOINT [ "python" ]