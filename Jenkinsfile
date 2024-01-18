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
                echo $(pwd)
                git config --global --add safe.directory $(pwd)
                git init .
                git status
                ls -l .
                python -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                pip install pre-commit
                git config --unset-all core.hooksPath
                pre-commit install
                pre-commit run --files mic/**/*
                pre-commit run --from-ref origin/HEAD --to-ref HEAD
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