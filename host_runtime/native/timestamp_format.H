// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENBEXI_V08_TIMESTAMP_FORMAT_H
#define OPENBEXI_V08_TIMESTAMP_FORMAT_H
#include <charconv>
#include <string>

// Preserve the legacy decimal spelling and *prefix* zero padding, even for
// unusual signed values. The caller owns the target; no clock value is cached.
template<class Date>
static void v08_format_timestamp(std::string& output,const Date& date,int format) {
    output.clear();
    auto number=[&](int value,size_t width) {
        char buffer[32];const auto result=std::to_chars(buffer,buffer+sizeof(buffer),value);
        const auto size=static_cast<size_t>(result.ptr-buffer);
        if(size<width)output.append(width-size,'0');
        output.append(buffer,size);
    };
    number(date.year,0);
    if(format==TIME_FORMAT_DOT) {
        output+='.';number(date.yday,3);output+='.';
        number(date.hours,2);output+='.';number(date.minutes,2);output+='.';
        number(date.seconds,2);
    }else {
        const char separator=format==TIME_FORMAT_SLASH?'/':'-';
        output+=separator;number(date.month,2);output+=separator;number(date.day,2);
        output+=' ';number(date.hours,2);output+=':';number(date.minutes,2);
        output+=':';number(date.seconds,2);
    }
}
#endif
