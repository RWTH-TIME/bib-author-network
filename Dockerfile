FROM python:3.13

COPY requirements.txt ./ 

RUN pip install --trusted-host pypi.python.org -r requirements.txt

COPY . ./

# run the project
CMD ["python3", "-m", "main"]
