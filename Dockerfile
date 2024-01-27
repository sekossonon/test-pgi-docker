FROM sek990/odoo-base:16.0

COPY ./src/odoo /odoo/src/odoo
COPY ./src/projects/odoo-common /odoo/custom_addons/16.0/odoo-common
COPY ./src/projects/project /odoo/custom_addons/16.0/project
COPY ./src/projects/mic /odoo/custom_addons/16.0/mic

RUN apt-get update \
    && apt install -y --no-install-recommends \
      postgresql-common \
      postgresql-client \
      wkhtmltopdf \
    && apt-get clean

RUN pip install -e /odoo/src/odoo

COPY ./install/ /tmp/install
RUN /tmp/install/install_requirements.sh && rm -rf /tmp/install


ENV ADDONS_PATH=/odoo/src/odoo/addons,/odoo/src/odoo/odoo/addons/,/odoo/custom_addons/16.0/odoo-common,/odoo/custom_addons/16.0/mic
