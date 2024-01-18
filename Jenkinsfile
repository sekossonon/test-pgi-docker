pipeline {
    agent {
        docker { image 'python:bullseye' }
    }

    stages {
        stage('Setting up virtual env') {
            steps {
                echo 'creating virtual env and install pre-commit'
                sh '''
                #!/usr/bin/bash
                cd mic
                python -m venv venv
                source venv/bin/activate
                pip install --upgrade pip
                pip install pre-commit
                sudo pre-commit install
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