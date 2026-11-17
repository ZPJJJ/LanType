# SPDX-FileCopyrightText: 2015 - 2024 Rime community
#
# SPDX-License-Identifier: GPL-3.0-or-later

set(BOOST_VERSION 1.89.0)

if(NOT EXISTS "${CMAKE_SOURCE_DIR}/boost/CMakeLists.txt")
  message(FATAL_ERROR "Restore the hash-locked Boost source with scripts/restore-native-sources.py before configuring CMake.")
endif()

# The CMake adaptor may not include header-only Boost libraries.
# Ensure all header-only targets exist to satisfy transitive dependencies.
set(BOOST_INCLUDE_LIBRARIES
    algorithm
    crc
    dll
    interprocess
    range
    regex
    scope_exit
    signals2
    utility
    uuid)

add_subdirectory(boost EXCLUDE_FROM_ALL)

# Create INTERFACE IMPORTED targets for any Boost::* library that is
# referenced as a dependency but not provided by the CMake adaptor.
set(__boost_header_only_libs
    algorithm any array assert bind concept_check config container_hash
    conversion core crc detail foreach function integer io iterator
    lexical_cast move mp11 mpl multi_index numeric_conversion optional
    predef preprocessor range rational scope_exit signals2 smart_ptr
    static_assert system throw_exception tti tuple type_index type_traits
    typeof utility variant variant2)
foreach(__boost_lib ${__boost_header_only_libs})
  if(NOT TARGET "Boost::${__boost_lib}")
    add_library("Boost::${__boost_lib}" INTERFACE IMPORTED GLOBAL)
  endif()
endforeach()
