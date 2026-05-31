import os

PROJECT_BASE = os.getenv("RAG_PROJECT_BASE") or os.getenv("RAG_DEPLOY_BASE")


def get_project_base_dir(*args) -> str:
    '''
    期望获取到的路径为："D:\\Users\\ALPHONSE\\VSCodeProjects\\swxy\\backend_cyl\\app\\rag"
    '''
    global PROJECT_BASE
    if not PROJECT_BASE:
        PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir,
            )
        )
    
    if args:
        return os.path.join(PROJECT_BASE, *args)
    return PROJECT_BASE


if __name__ == "__main__":
    print("Project Base Directory:", get_project_base_dir())