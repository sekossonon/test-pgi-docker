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
                git config --global --add safe.directory $CI_PROJECT_DIR
                git init .
                git status
                ls -l .
                python -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                pip install pre-commit
                pre-commit install
                cat /root/.cache/pre-commit/pre-commit.log
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