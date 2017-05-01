#!/bin/bash
# Run this with no arguments for default functionality
# Run with anything as an argument and all maintainers and devices
# will be printed first, followed by regular functionality

updaterrepolocation="../updater"
wikirepolocation="../wiki"
jenkinsrepolocation="../jenkins"
showallmaintainers=false
if ! [ -z $1 ]; then showallmaintainers=true; fi
if ! [ -d $wikirepolocation ]; then
	echo "wiki folder you specified doesn't exist, quitting" 1>&2
	exit 1
fi
if ! [ -d $updaterrepolocation ]; then
	echo "updater folder you specified doesn't exist, quitting" 1>&2
	exit 1
fi
if ! [ -d $jenkinsrepolocation ]; then
	echo "jenkins folder you specified doesn't exist, quitting" 1>&2
	exit 1
fi
hudsonlist=$(cat $jenkinsrepolocation/lineage-build-targets | cut -f1 -d ' ' | sort | uniq | grep -v '^#' | grep -ve '^$')

# Print list of maintainers if told to
if [ $showallmaintainers == true ]; then
echo "## Maintainers of all devices in hudson according to the wiki:"
	for codename in $hudsonlist; do
		if [ -f $wikirepolocation/_data/devices/$codename.yml ]; then
			wiki_maintainers=$(grep maintainer $wikirepolocation/_data/devices/$codename.yml | cut -d ':' -f2 | awk '{$1=$1};1')
			if [[ $wiki_maintainers = *\[\'\'\]* ]]; then
				wiki_maintainers="no maintainers"
			fi
			wiki_maintainers=$(echo $wiki_maintainers | tr -d \[\])
			printf "%-15s%-40s\n" "$codename:" "$wiki_maintainers"
		fi
	done
printf "\n"
fi

# Check if a wiki page exists for each device
echo "## Devices present in hudson, but have no wiki page:"
wikipagefail=0
for codename in $hudsonlist; do
	if ! [ -f $wikirepolocation/_data/devices/$codename.yml ]; then
		echo $codename
		((wikipagefail++))
	fi
done
if [ $wikipagefail = 0 ]; then echo "none"; else echo "total = $wikipagefail"; fi
printf "\n"

# Check devices that have a wiki page have maintainers
echo "## Devices present in hudson, but with no maintainers on the wiki:"
wikimaintainerfail=0
for codename in $hudsonlist; do
	if [ -f $wikirepolocation/_data/devices/$codename.yml ]; then
		WIKI_MAINTAINERS=$(grep maintainer $wikirepolocation/_data/devices/$codename.yml | cut -d ':' -f2 | awk '{$1=$1};1')
		if [[ $WIKI_MAINTAINERS = *\[\'\'\]* ]]; then
			echo $codename
			((wikimaintainerfail++))
		fi
		unset WIKI_MAINTAINERS
	fi
done
if [ $wikimaintainerfail = 0 ]; then echo "none"; else echo "total = $wikimaintainerfail"; fi
printf "\n"

# Check devices that have a wiki page but no install_method
echo "## Devices present in hudson, but with install_method set as TODO on the wiki:"
wikiinstallmethodfail=0
for codename in $hudsonlist; do
	if [ -f $wikirepolocation/_data/devices/$codename.yml ]; then
		wiki_installmethod=$(grep install_method $wikirepolocation/_data/devices/$codename.yml | cut -d ':' -f2)
		if [[ $wiki_installmethod = *TODO* ]]; then
			echo $codename
			((wikiinstallmethodfail++))
	fi
	unset wiki_installmethod
	fi
done
if [ $wikiinstallmethodfail = 0 ]; then echo "none"; else echo "total = $wikiinstallmethodfail"; fi
printf "\n"

# Check that devices have an update page
echo "## Devices present in hudson, but don't have an update page:"
updaterfail=0
for codename in $hudsonlist; do
	if [ -f $updaterrepolocation/devices.json ]; then
		if ! grep -q "model\": \"$codename\"" $updaterrepolocation/devices.json; then
			echo $codename
			((updaterfail++))
		fi
	else
		echo "$updaterrepolocation/devices.json doesn't exist"
		((updaterfail++))
	fi
done
if [ $updaterfail = 0 ]; then echo "none"; else echo "total = $updaterfail"; fi
