coverage run test.py
ret=$?
coverage xml -o coverage-reports/coverage.xml
coverage report
exit $ret