property serverPID : ""

on run
	set resourcesFolder to POSIX path of (path to me) & "Contents/Resources/"
	set launchScript to resourcesFolder & "launch.sh"
	
	try
		-- Run the shell script in the background and capture its PID
		set serverPID to do shell script "bash " & quoted form of launchScript & " > /dev/null 2>&1 & echo $!"
		
		-- Wait 2 seconds for server to start, then open browser
		do shell script "sleep 2 && open 'http://127.0.0.1:8005'"
	end try
end run

on quit
	if serverPID is not "" then
		try
			do shell script "kill " & serverPID
		end try
	end if
	continue quit
end quit
