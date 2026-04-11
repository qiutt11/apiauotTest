pipeline {
    agent any
    parameters {
        choice(name: 'ENV', choices: ['test', 'dev', 'staging'], description: '测试环境')
        string(name: 'TEST_PATH', defaultValue: 'testcases/', description: '用例路径')
        choice(name: 'REPORT', choices: ['allure', 'html', 'both'], description: '报告类型')
    }
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh "python run.py --env ${params.ENV} --path ${params.TEST_PATH} --report ${params.REPORT}"
            }
        }
        stage('Report') {
            steps {
                allure includeProperties: false, results: [[path: 'reports/allure-results']]
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'reports/**', fingerprint: true
            archiveArtifacts artifacts: 'logs/**', fingerprint: true
        }
    }
}
