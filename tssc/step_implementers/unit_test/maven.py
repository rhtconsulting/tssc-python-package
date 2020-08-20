"""Step Implementer for the unit-test step for Maven generating JUnit reports.

Step Configuration
------------------

Step configuration expected as input to this step.
Could come from either configuration file or
from runtime configuration.

| Configuration Key  | Required? | Default     | Description
|--------------------|-----------|-------------|-----------
| `fail-on-no-tests` | True      | True        | Value to specify whether unit-test
                                                 step can succeed when no tests are defined
| `pom-file`         | True      | `'pom.xml'` | pom used to run tests and check
                                                 for existence of custom reportsDirectory

Expected Previous Step Results
------------------------------

Results expected from previous steps that this step requires.

None.

Results
-------

Results output by this step.

| Result Key         | Description
|--------------------|------------
| `result`           | A dictionary describing the unit test step results
| `options`          | A dictionary of non-standard options used by this step implementer
| `report-artifacts` | An array of dictionaries describing artifacts \
                       generated by this step implementer

**result**
Keys in the `result` dictionary element in the `unit-test` dictionary of the step results.

| `result` Key | Description
|--------------|------------
| `success`    | Boolean value describing success/failure of this step
| `message`    | Human readable message describing results of this step

**options**
Keys in the `options` dictionary element in the `unit-test` dictionary of the step results.

| `options` Key       | Description
|---------------------|------------
| `pom-path`          | Absolute path to the pom used to run tests
| `fail-on-no-tests`  | Boolean value describing whether or not step should fail \
                        when unit tests are missing

**report-artifacts**
Keys in the `report-artifacts` dictionary element in the `unit-test` dictionary of the step results.

| `report-artifacts` Key | Description
|------------------------|------------
| `name`                 | Human readable name for report artifact generated by this step
| `path`                 | Absolute path (including transport protocol) to the step report artifact
"""
import sys
import os
from xml.etree import ElementTree
import re
import sh

from tssc import TSSCFactory
from tssc import StepImplementer
from tssc import DefaultSteps

DEFAULT_CONFIG = {
    'fail-on-no-tests': True,
    'pom-file': 'pom.xml'
}

REQUIRED_CONFIG_KEYS = [
    'fail-on-no-tests',
    'pom-file'
]

class Maven(StepImplementer):
    """
    StepImplementer for the unit-test step for Maven generating JUnit reports.
    """

    @staticmethod
    def step_name():
        """
        Getter for the TSSC Step name implemented by this step.

        Returns
        -------
        str
            TSSC step name implemented by this step.
        """
        return DefaultSteps.UNIT_TEST

    @staticmethod
    def step_implementer_config_defaults():
        """
        Getter for the StepImplementer's configuration defaults.

        Notes
        -----
        These are the lowest precedence configuration values.

        Returns
        -------
        dict
            Default values to use for step configuration values.
        """
        return DEFAULT_CONFIG

    @staticmethod
    def required_runtime_step_config_keys():
        """
        Getter for step configuration keys that are required before running the step.

        See Also
        --------
        _validate_runtime_step_config

        Returns
        -------
        array_list
            Array of configuration keys that are required before running the step.
        """
        return REQUIRED_CONFIG_KEYS

    def _run_step(self, runtime_step_config):
        """
        Runs the TSSC step implemented by this StepImplementer.

        Parameters
        ----------
        runtime_step_config : dict
            Step configuration to use when the StepImplementer runs the step with all of the
            various static, runtime, defaults, and environment configuration munged together.

        Returns
        -------
        dict
            Results of running this step.
        """
        pom_file = runtime_step_config['pom-file']
        fail_on_no_tests = runtime_step_config['fail-on-no-tests']

        if not os.path.exists(pom_file):
            raise ValueError('Given pom file does not exist: ' + pom_file)

        maven_surefire_plugin = self.find_reference_in_pom(pom_file, 'maven-surefire-plugin')
        if maven_surefire_plugin is None:
            raise ValueError('Unit test dependency "maven-surefire-plugin" missing from POM.')

        reports_dir = self.find_reference_in_pom(pom_file, 'reportsDirectory')
        if reports_dir is not None:
            test_results_dir = reports_dir
        else:
            test_results_dir = os.path.join(
                os.path.dirname(os.path.abspath(pom_file)),
                'target/surefire-reports')

        try:
            sh.mvn(  # pylint: disable=no-member
                'clean',
                'test',
                '-f', pom_file,
                _out=sys.stdout
            )
        except sh.ErrorReturnCode as error:
            raise RuntimeError("Error invoking mvn: {error}".format(error=error))

        test_results_output_path = test_results_dir

        if not os.path.isdir(test_results_dir) or \
            len(os.listdir(test_results_dir)) == 0:
            if fail_on_no_tests is not True:
                results = {
                    'result': {
                        'success': True,
                        'message': 'unit test step run successfully, but no tests were found'
                    },
                    'options': {
                        'pom-path': pom_file,
                        'fail-on-no-tests': False
                    }
                }
            else:# pragma: no cover
                # Added 'no cover' to bypass missing unit-test step coverage error
                # that is covered by the following unit test:
                #   test_unit_test_run_attempt_fails_fail_on_no_tests_flag_true
                raise RuntimeError('Error: No unit tests defined')
        else:
            results = {
                'result': {
                    'success': True,
                    'message': 'unit test step run successfully and junit reports were generated'
                },
                'options': {
                    'pom-path': pom_file
                },
                'report-artifacts': [
                    {
                        'name': 'maven unit test results generated using junit',
                        'path': f'file://{test_results_output_path}'
                    }
                ]
            }
        return results

    @staticmethod
    def find_reference_in_pom(pom_file, reference):
        """ Return the report directory specified in the pom """
        # extract and set namespace
        xml_file = ElementTree.parse(pom_file).getroot()
        xml_namespace_match = re.findall(r'{(.*?)}', xml_file.tag)
        xml_namespace = xml_namespace_match[0] if xml_namespace_match else ''
        maven_xml_namespace_dict = {'maven': xml_namespace}

        if reference == 'maven-surefire-plugin':
            xpath = 'maven:build/'\
                    'maven:plugins/'\
                    'maven:plugin/'\
                    '[maven:artifactId="maven-surefire-plugin"]/'
        elif reference == 'reportsDirectory':
            xpath = 'maven:build/'\
                    'maven:plugins/'\
                    'maven:plugin/'\
                    '[maven:artifactId="maven-surefire-plugin"]/'\
                    'maven:configuration/'\
                    'maven:reportsDirectory'

        result = xml_file.find(xpath, maven_xml_namespace_dict)
        return None if result is None else result.text

# register step implementer
TSSCFactory.register_step_implementer(Maven)