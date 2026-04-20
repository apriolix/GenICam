"""Setup configuration for GenICam ROS2 Package.

This setup file configures the Python package for installation and distribution.
It defines package metadata, dependencies, and entry points.
"""

from setuptools import find_packages, setup

package_name = 'genicam_ros'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='benjamin',
    maintainer_email='benjamin.dilly@stud.hshl.de',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)
