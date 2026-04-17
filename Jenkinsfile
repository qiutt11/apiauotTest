pipeline {
    agent any
    parameters {
        choice(name: 'ENV', choices: ['test', 'dev', 'staging'], description: '测试环境')
        string(name: 'TEST_PATH', defaultValue: 'testcases/', description: '用例路径')
        choice(name: 'REPORT', choices: ['allure', 'html', 'both'], description: '报告类型')
        string(name: 'LEVEL', defaultValue: '', description: '优先级过滤（可选）：P0 / P0,P1 / 留空运行全部')
        string(name: 'WORKERS', defaultValue: '', description: '并行进程数（可选）：数字 / auto / 留空单进程')
    }
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                script {
                    def cmd = "python run.py --env ${params.ENV} --path ${params.TEST_PATH} --report ${params.REPORT}"
                    if (params.LEVEL?.trim()) {
                        cmd += " --level ${params.LEVEL}"
                    }
                    if (params.WORKERS?.trim()) {
                        cmd += " --workers ${params.WORKERS}"
                    }
                    sh cmd
                }
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
