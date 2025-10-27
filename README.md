**Alert system**

This is a solution for checking parameters and availibity web-sites by curl request. 
You have multiply ways to control: 
 - site status 
 - contain key word in answer
 - check left days for SSL-sertificates
 - extract value from answer and compare value with treshold 

**How to install**
 1. Clone or donwload project. Rename file config.yml.sample to config.yml:
```bash
mv config.yml.sample config.yml
```
 2. change config.yml in accordance to example
 3. run conteiner from directory with project
```bash
docker compose up -d
```

