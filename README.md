# allure‑emailer

**allure‑emailer** is a small Python command‑line tool that makes it easy to send
Allure test run summaries via email directly from your continuous
integration (CI) pipelines.  It parses the Allure summary JSON produced
by your test run, formats a short HTML summary and delivers it to one or
more recipients using your SMTP server.  The tool can be used in any
CI system (Jenkins, GitHub Actions, GitLab CI and others) and is
packaged for convenient installation via `pip`.

## Features

* 📦 **Easy installation** – distributed on PyPI so you can install it
  with `pip install allure‑emailer`.
* 🧭 **Interactive configuration** – run `allure‑emailer init` once to
  walk you through choosing an authentication method—SMTP with a
  password, SMTP with an OAuth2 token or Microsoft Graph—and then
  collect the appropriate settings (SMTP host/port/user/password or
  OAuth2 token, or tenant/client credentials for Graph).  It will also
  ask for the recipient addresses, the path to the Allure summary JSON
  and your Allure report URL.  The generated configuration file uses
  unique variable names prefixed with ``AEMAILER_`` (for example
  ``AEMAILER_HOST`` and ``AEMAILER_TENANT_ID``) to avoid collisions
  with system environment variables.  The tool never overwrites an
  existing `.env` file; if one is present, the settings will instead
  be written to `.env.emailer`.  The "From" address is inferred from
  your SMTP username by default when using SMTP.  When you choose
  port `465` the tool will connect via SSL; for port `587` it will use
  STARTTLS.
* ✉️ **Send test summaries** – run `allure‑emailer send` in a CI step
  after generating the Allure report.  It reads the configuration from
  `.env.emailer` if present, otherwise from `.env`, parses the summary
  JSON and sends a concise HTML email showing the total number of tests,
  how many passed, failed, were broken or skipped, together with a link
  to the full report.  Configuration values are read first from
  variables prefixed with ``AEMAILER_`` (such as ``AEMAILER_HOST`` and
  ``AEMAILER_PORT``) and fall back to legacy unprefixed variables if
  necessary.  You can override any configuration value via
  command‑line options.  The subject line can be customised with
  `--subject` (which supports environment variable placeholders) and
  you can inject additional key–value pairs into the email body with
  `--field KEY=VALUE` or by defining `AEMAILER_FIELD_<KEY>=VALUE` entries in your
  configuration file.  (The legacy `FIELD_<KEY>` prefix is still
  recognised for backward compatibility.)
* 🔐 **OAuth 2.0 support** – if your email provider requires OAuth2
  authentication you have two options:
  
  * **SMTP XOAUTH2** – provide a bearer access token via the
    `AEMAILER_OAUTH_TOKEN` variable in your configuration file or the
    `--oauth-token` option when sending.  When an OAuth token is
    supplied the regular SMTP password is ignored and XOAUTH2 is used
    to authenticate over SMTP (useful for Gmail, etc.).
  * **Microsoft Graph API** – instead of SMTP you can send via the
    Microsoft Graph API by defining `AEMAILER_TENANT_ID`,
    `AEMAILER_CLIENT_ID` and `AEMAILER_CLIENT_SECRET` (and optionally
    `AEMAILER_FROM_ADDRESS`) in your configuration.  When these
    variables are present the tool obtains an access token from
    Azure Active Directory and invokes the Graph API to send your
    message.  You can also override these values at run time with
    `--tenant-id`, `--client-id`, `--client-secret` and `--from-address`.
* 🧑‍🤝‍🧑 **Multiple recipients** – specify a comma‑separated list of
  recipient addresses either in your `.env` file or on the command
  line.
* ✅ **Works everywhere** – designed to integrate easily with
  Jenkins, GitHub Actions, GitLab CI and other CI systems; no
  assumptions about your environment.

## Installation

```
pip install allure-emailer
```

The tool requires Python 3.7 or newer.  The installation pulls in
`typer` for the CLI and `python-dotenv` for configuration
management.  The Python standard library’s `smtplib` and `email`
modules are used to send messages and therefore no extra
dependencies are needed for SMTP.

## Quick start

1. **Generate a configuration** – run the following command inside
   your project repository to create a configuration file with your
   SMTP and email settings:

   ```shell
   allure-emailer init
   ```

   You will be prompted for:

   - **SMTP host** – e.g. `smtp.gmail.com` or your corporate SMTP
     server.
   - **SMTP port** – the port to connect on; `587` is the standard
     STARTTLS port.
   - **SMTP username and password** – credentials for logging into your
     SMTP server.  Use an application password if your provider
     supports it.  **The SMTP username must be the full email
     address** (for example `contact@example.com`) and will be used
     as the “From” address unless overridden when sending.  If the
     username does not contain an `@` symbol the tool will refuse to
     send email.
   - **Recipient email addresses** – one or more addresses separated by
     commas.
   - **Path to the Allure summary JSON** – defaults to
     `allure-report/widgets/summary.json`, which is where the Allure
     command‐line tool writes its summary.
   - **Allure report URL** – a publicly accessible URL to the full
     report (for example, an artifact link or a published report).

   When specifying the SMTP port keep in mind that port **465**
   expects an implicit SSL connection (``smtplib.SMTP_SSL``), whereas
   port **587** uses the more common STARTTLS upgrade.  The tool
   automatically chooses the correct connection method based on the
   port number.

   The answers are written to `.env` in your working directory if
   no `.env` already exists.  If a `.env` file is present it will
   **not** be overwritten; instead a new `.env.emailer` file will be
   created for allure‑emailer’s settings.  When sending email the tool
   automatically prefers `.env.emailer` over `.env` if both are
   available.

2. **Generate an Allure report** – run your tests and generate the
   report as you normally would.  For example, using Maven:

   ```shell
   mvn clean test
   allure serve target/allure-results  # or allure generate …
   ```

3. **Send the summary** – after the report is generated, invoke the
   `send` subcommand:

   ```shell
   allure-emailer send
   ```

   This will read the configuration from `.env.emailer` if it
   exists, otherwise from `.env`, parse the summary JSON specified
   therein, construct an HTML email and send it using the configured
   SMTP server.  The subject line will be “Allure Test Summary” and
   the message body contains a small table summarising total,
   passed, failed, broken and skipped tests, along with a link to
   your full report.  The sender address defaults to the SMTP
   username; you can override it using the ``--sender`` option when
   running ``send``.

### Command‑line overrides

All settings stored in your configuration file can be overridden at
the point of sending.  This is handy if you want to use different
credentials or recipients in certain CI pipelines.  The
``--env-file`` option allows you to choose a different config file.
For example:

```shell
allure-emailer send \
  --env-file my_other.env \
  --recipients user1@example.com,user2@example.com \
  --host smtp.example.com --port 2525 \
  --user ci-bot --password "$SMTP_PASSWORD" \
  --sender ci@example.com \
  --json-path custom/summary.json \
  --report-url https://ci.example.com/artifacts/allure-report/index.html
```

## Jenkins pipeline example

In a Jenkins declarative pipeline, you can send a summary after
running your tests.  This example assumes you have already installed
Python and `allure-emailer` on your Jenkins agent:

```groovy
pipeline {
    agent any
    stages {
        stage('Test') {
            steps {
                sh 'pytest --alluredir=allure-results'
                sh 'allure generate allure-results --clean -o allure-report'
            }
        }
        stage('Email summary') {
            steps {
                sh 'allure-emailer send'
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'allure-report/**', fingerprint: true
        }
    }
}
```

The configuration file (`.env` or `.env.emailer`) should be checked
into your repository or otherwise made available on the Jenkins agent
before the `send` step.  If both exist the tool will use
`.env.emailer`.

## GitHub Actions example

Here is a minimal GitHub Actions workflow that runs tests, builds
an Allure report and sends an email summary:

```yaml
name: Test and email summary
on:
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        pip install pytest allure-pytest allure-emailer
    - name: Run tests
      run: |
        pytest --alluredir=allure-results
        allure generate allure-results --clean -o allure-report
    - name: Send email summary
      env:
        SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
      run: |
        allure-emailer send --password "$SMTP_PASSWORD"
```

Place your configuration file (`.env` or `.env.emailer`) in the
repository root or specify its location via the `--env-file` option.
Sensitive values such as your SMTP password should be stored in
GitHub Secrets and referenced with `$SMTP_PASSWORD` as shown.

## GitLab CI example

In GitLab CI, you can add a job to send the email after your test job:

```yaml
stages:
  - test
  - email

test:
  stage: test
  script:
    - pip install pytest allure-pytest allure-emailer
    - pytest --alluredir=allure-results
    - allure generate allure-results --clean -o allure-report
  artifacts:
    paths:
      - allure-report/

email:
  stage: email
  dependencies:
    - test
  script:
    - pip install allure-emailer
    - allure-emailer send
  only:
    - main
```

Ensure that your `.env` file is available in the working directory
before running the email job (for example by committing it to your
repository, storing it in a project variable, or injecting it via
`before_script`).

## Custom subject and additional fields

Sometimes you need to include extra context in your email notifications
or customise the subject line to include identifiers from your CI
environment.  The `send` command provides two mechanisms to achieve
this:

### Custom subject

You can override the default subject (``"Allure Test Summary"``)
by passing the ``--subject`` option.  The value passed may contain
placeholders for environment variables using the `$VAR` or `${VAR}`
syntax; these will be expanded at runtime using the current environment
and any values defined in your configuration file.  For example:

```shell
allure-emailer send --subject "Build $CI_PIPELINE_ID - Allure summary"
```

If ``CI_PIPELINE_ID`` is defined in the environment or in
`.env.emailer`, it will be replaced with its value.

### Custom fields

Additional key–value pairs can be included in the body of the email.
Specify them on the command line using the ``--field KEY=VALUE``
option (you can use this option multiple times) or define them in
your configuration file with variables prefixed by ``AEMAILER_FIELD_``.
The new prefix avoids collisions with other environment variables.  A
legacy ``FIELD_`` prefix is also supported for backward compatibility.
These fields will be displayed under an “Additional Information” section
in the email.  For example:

```shell
allure-emailer send \
  --field BUILD_NUMBER=42 \
  --field COMMIT=abcdef123
```

or, in `.env.emailer`:

```
AEMAILER_FIELD_BUILD_NUMBER=42
AEMAILER_FIELD_COMMIT=abcdef123
```

Both methods are supported simultaneously; command‑line fields take
precedence over those defined in the file if there are conflicts.

### OAuth 2.0 authentication

Some email providers (notably Gmail and Microsoft 365) no longer
accept basic username/password authentication and instead require
OAuth 2.0 (XOAUTH2).  **allure‑emailer** supports this by allowing you to
provide OAuth2 credentials in two different ways.

1. **SMTP XOAUTH2** – if you have generated an access token for your
   SMTP account, set it in your configuration file using the
   variable `AEMAILER_OAUTH_TOKEN` (prefixed to avoid collisions).
   When this variable is present the configured SMTP password will be
   ignored and the token will be used for XOAUTH2 authentication.  You
   can also pass a token directly on the command line using the
   `--oauth-token` flag:

```shell
```shell
allure-emailer send \
  --oauth-token "$SMTP_ACCESS_TOKEN"
```

2. **Microsoft Graph API** – if you wish to send mail via the
   Microsoft Graph API instead of SMTP, define the variables
   `AEMAILER_TENANT_ID`, `AEMAILER_CLIENT_ID` and
   `AEMAILER_CLIENT_SECRET` (and optionally `AEMAILER_FROM_ADDRESS`) in
   your configuration.  When these values are present the tool will
   obtain an access token from Azure Active Directory and invoke the
   Graph API endpoint `https://graph.microsoft.com/v1.0/users/{FROM}/sendMail`
   to deliver your message.  You can override these values on the
   command line with `--tenant-id`, `--client-id`, `--client-secret` and
   `--from-address`.

Obtaining OAuth2 tokens usually requires registering an application
with your email provider and exchanging a refresh token for an access
token via their API.  This tool does **not** perform that exchange for
you; it expects a valid bearer token (for SMTP) or valid client
credentials (for Graph).  Refer to your provider’s documentation on
how to create and refresh tokens.

## Development and testing

This repository contains a small test suite under `tests/` which can
be run with [`pytest`](https://pytest.readthedocs.io/).  To run the
tests locally, first install the package in editable mode:

```shell
pip install -e .[dev]
pytest
```

The CLI is implemented using
[Typer](https://typer.tiangolo.com/), which builds on Click.  For
more information on extending the CLI or contributing to
`allure-emailer`, please refer to the source code under
`src/allure_emailer/`.

## License

This project is distributed under the terms of the MIT license.  See
the file [`LICENSE`](LICENSE) for full details.