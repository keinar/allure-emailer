# allure‑emailer

[![PyPI version](https://badge.fury.io/py/allure-emailer.svg)](https://badge.fury.io/py/allure-emailer)

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
  generate a configuration file containing your SMTP credentials
  (including the **full email address** for the username), recipient
  addresses, the path to the Allure summary JSON and your Allure
  report URL.  The tool never overwrites an existing `.env` file;
  if one is present, the settings will instead be written to
  `.env.emailer`.  The "From" address is inferred from your SMTP
  username by default.  When you choose port `465` the tool will
  connect via SSL; for port `587` it will use STARTTLS.
* ✉️ **Send test summaries** – run `allure‑emailer send` in a CI step
  after generating the Allure report.  It reads the configuration from
  `.env.emailer` if present, otherwise from `.env`, parses the summary
  JSON and sends a concise HTML email showing the total number of tests,
  how many passed, failed, were broken or skipped, together with a link
  to the full report.  You can override any configuration value via
  command‑line options.  The subject line can be customised with
  `--subject` (which supports environment variable placeholders) and
  you can inject additional key–value pairs into the email body with
  `--field KEY=VALUE` or by defining `FIELD_<KEY>=VALUE` entries in your
  configuration file.
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

> Note: Never commit your SMTP password or secrets to source control. Always use CI secrets/environment variables for sensitive values.

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
your configuration file with variables prefixed by ``FIELD_``.  These
fields will be displayed under an “Additional Information” section in
the email.  For example:

```shell
allure-emailer send \
  --field BUILD_NUMBER=42 \
  --field COMMIT=abcdef123
```

or, in `.env.emailer`:

```
FIELD_BUILD_NUMBER=42
FIELD_COMMIT=abcdef123
```

Both methods are supported simultaneously; command‑line fields take
precedence over those defined in the file if there are conflicts.

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