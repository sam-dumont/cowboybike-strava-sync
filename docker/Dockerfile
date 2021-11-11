FROM python:3.9-alpine

RUN addgroup -S synchro && adduser -S synchro -G synchro
USER synchro
WORKDIR /home/synchro

# Copy function code
COPY src ./src

RUN pip install -r ./src/requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "python" "src/main.py" ]