pipeline {
    agent {
        docker { image 'python:bullseye' }
    }

    stages {
        stage('Setting up virtual env') {
            steps {
                echo 'creating virtual env and install pre-commit'
                sh '''
                pip install pre-commit
                cd mic
                pre-commit install
                '''
            }
        }
        stage('Running pre-commit') {
            steps {
                echo 'running pre-commit'
                sh '''
                pre-commit run --all-files
                '''
            }
        }
    }
}