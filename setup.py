from setuptools import setup

def main() -> None:
    name = 'piproe'
    setup(
        name=name,
        zip_safe=False,
        py_modules=[name],
    )


if __name__ == '__main__':
    main()
