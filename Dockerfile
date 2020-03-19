FROM ubuntu:14.04
MAINTAINER software@louisenhof2.de

ENV DEBIAN_FRONTEND noninteractive

# adjust the next line, replace nas by you local mirror or comment it out
#RUN sed -i.save "s/archive.ubuntu.com/nas/g" /etc/apt/sources.list 

RUN apt-get update && apt-get -y install wget && apt-get clean 
RUN wget http://repo.continuum.io/archive/Anaconda-2.1.0-Linux-x86_64.sh -O /anaconda
RUN bash anaconda -b -p /opt/anaconda && rm anaconda
ENV PATH /opt/anaconda/bin:$PATH
RUN conda update --yes --all && conda clean --yes --tarballs

RUN conda install --yes seaborn basemap && conda clean --yes --tarballs
RUN pip install https://github.com/quantenschaum/ctplot/archive/master.zip

RUN adduser --disabled-password --gecos '' ctplot 
USER ctplot 

EXPOSE 8080
CMD ["ctserver"]
