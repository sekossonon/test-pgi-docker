pipeline {
    agent {
        docker { 
            image 'python:bullseye'
            args '-u root --privileged'
        }
    }

    stages {
        stage('Setting up virtual env') {
            steps {
                echo 'creating virtual env and install pre-commit'
                sh '''
                git init .
                cat /root/.cache/pre-commit/pre-commit.log
                ls -l .
                python -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                pip install pre-commit
                pre-commit install
                '''
            }
        }
        stage('Running pre-commit') {
            steps {
                echo 'running pre-commit'
                sh '''
                pre-commit run --files mic/**/*
                pre-commit run --from-ref origin/HEAD --to-ref HEAD
                '''
            }
        }
    }
}