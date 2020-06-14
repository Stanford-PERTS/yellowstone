from google.appengine.api import urlfetch
import jinja2
import json
import logging

from core import SecretValue
import config
import markdown
import util


# Setup jinja2 environment using the email subdirectory in templates
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates/emails'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def render_markdown(markdown_string):
    """Chris added this to Matt's mandrill code for older platforms that used
    hard-coded markdown email templates rather than jinja templates."""
    return markdown.markdown(markdown_string)


def send(template_data={}, **kwargs):

    subject = render(kwargs['subject'], **template_data)

    # Determine if using html string or a template
    body = ''
    if 'body' in kwargs:
        body = render(kwargs['body'], **template_data)
    elif 'template' in kwargs:
        body = render_template(kwargs['template'], **template_data)

    # JSON for Mandrill HTTP POST request
    json_mandrill = {
        # "key": this is added later, to make sure it's not logged.
        "message": {
            "html": body,
            "subject": subject,
            "from_email": config.from_yellowstone_email_address,
            "from_name": "PERTS",
            "inline_css": True,
            "to": format_to_address(kwargs['to_address'])
        }
    }

    # Determine if message should send
    if util.is_development() and not config.should_deliver_smtp_dev:
        logging.info('Email not sent, check config!')
        logging.info(json_mandrill)
        return None

    api_key = SecretValue.get_by_key_name('mandrill_api_key').value
    if api_key is None:
        raise Exception("No SecretValue set for 'mandrill_api_key'")
    json_mandrill['key'] = api_key

    # URL for Mandrill HTTP POST request
    url = "https://mandrillapp.com/api/1.0/messages/send.json"
    rpc = urlfetch.create_rpc()
    urlfetch.make_fetch_call(
        rpc,
        url=url,
        payload=json.dumps(json_mandrill),
        method=urlfetch.POST,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    try:
        result = rpc.get_result()
        if result.status_code == 200:
            text = result.content
    except urlfetch.DownloadError:
        # Request timed out or failed.
        logging.error('Email failed to send.')
        result = None
    return result


# Formats the "to" field to fit conventions
def format_to_address(unformatted_to):
    formatted_to = []
    # Handles list of strings or single string
    for email in unformatted_to if not isinstance(unformatted_to, basestring) else [unformatted_to]:
        formatted_to.append({
            "email": email,
            "type": "to"
        })
    return formatted_to


# Creates email html from a string using jinja2
def render(s, **template_data):
    return jinja2.Environment().from_string(s).render(**template_data)


# Loads email html from a template using jinja2
def render_template(template, **template_data):
    return JINJA_ENVIRONMENT.get_template(template).render(**template_data)
