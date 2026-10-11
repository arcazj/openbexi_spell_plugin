// SPDX-License-Identifier: GPL-3.0-or-later
#include <string>
// The original process manager uses bash -c. Quote each generated argument
// once, retaining literal spaces, apostrophes and shell metacharacters.
static std::string SPELLquoteArgument(const std::string& value)
{
    std::string result="'";
    for (char ch:value) {
        if (ch=='\'') result+="'\\''";
        else result+=ch;
    }
    return result+"'";
}
