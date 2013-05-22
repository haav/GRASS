CFLAGS="-g -Wall" ./configure \
--with-odbc=yes --with-cairo=yes --with-gdal=yes \
--with-geos=/usr/bin/geos-config --with-wxwidgets=/usr/bin/wx-config \
--with-python=yes --with-freetype-includes=/usr/include/freetype2 \
--with-tcltk-includes=/usr/include/tcl8.5 \
--with-proj-share=/usr/share/proj \
--with-cxx --with-freetype=yes \
--with-postgres=no --with-sqlite=yes --enable-largefile=yes \
--with-readline