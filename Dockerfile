FROM microcom/odoo-base:16

#last commit hash bc1ad08286be9bb02d111e49fe095879b649449e
COPY ./odoo /odoo/src/odoo
COPY ./odoo-common /odoo/custom_addons/16.0/odoo-common
COPY ./projects /odoo/custom_addons/16.0/projects
COPY ./mic /odoo/custom_addons/16.0/mic


RUN apt-get update
RUN apt install -y postgresql-common postgresql-client
RUN apt-get install --no-install-recommends -y wkhtmltopdf
RUN apt-get clean

RUN \
  pip install --no-cache-dir \
    -r /odoo/src/odoo/requirements.txt \
    -f https://wheelhouse.acsone.eu/manylinux2014 \
  && pip install -e /odoo/src/odoo
RUN pip install pyOpenSSL --upgrade

ENV ADDONS_PATH=/odoo/src/odoo/addons,/odoo/src/odoo/odoo/addons/